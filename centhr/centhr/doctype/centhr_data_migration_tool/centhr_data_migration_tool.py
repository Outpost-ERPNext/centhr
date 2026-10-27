# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.background_jobs import is_job_enqueued

from centhr.api.migrate.account import AccountMigrator
from centhr.api.migrate.additional_salary import AdditionalSalaryMigrator
from centhr.api.migrate.attendance import AttendanceMigrator
from centhr.api.migrate.base import get_error_message
from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.cost_center import CostCenterMigrator
from centhr.api.migrate.employee import EmployeeMigrator
from centhr.api.migrate.leave_allocation import LeaveAllocationMigrator
from centhr.api.migrate.leave_application import LeaveApplicationMigrator
from centhr.api.migrate.leave_policy import LeavePolicyMigrator
from centhr.api.migrate.leave_policy_assignment import LeavePolicyAssignmentMigrator
from centhr.api.migrate.leave_type import LeaveTypeMigrator
from centhr.api.migrate.payroll_entry import PayrollEntryMigrator
from centhr.api.migrate.salary_component import SalaryComponentMigrator
from centhr.api.migrate.salary_slip import SalarySlipMigrator
from centhr.api.migrate.salary_structure import SalaryStructureMigrator
from centhr.api.migrate.salary_structure_assignment import SalaryStructureAssignmentMigrator

TOOL = "Centhr Data Migration Tool"
DATA_LOG = "Centhr Data Log"
RUN_JOB = "centhr.centhr.doctype.centhr_data_migration_tool.centhr_data_migration_tool.run_migration"
PROGRESS_EVENT = "centhr_migration_progress"
STOPPED_EVENT = "centhr_migration_stopped"
MIGRATORS = {
	"account": AccountMigrator,
	"cost_center": CostCenterMigrator,
	"employee": EmployeeMigrator,
	"leave_type": LeaveTypeMigrator,
	"leave_policy": LeavePolicyMigrator,
	"leave_policy_assignment": LeavePolicyAssignmentMigrator,
	"leave_allocation": LeaveAllocationMigrator,
	"leave_application": LeaveApplicationMigrator,
	"attendance": AttendanceMigrator,
	"salary_component": SalaryComponentMigrator,
	"salary_structure": SalaryStructureMigrator,
	"salary_structure_assignment": SalaryStructureAssignmentMigrator,
	"additional_salary": AdditionalSalaryMigrator,
	"salary_slip": SalarySlipMigrator,
	"payroll_entry": PayrollEntryMigrator,
}


class CenthrDataMigrationTool(Document):
	pass


@frappe.whitelist()
def get_records(section: str, company: str, filters: str | dict | None = None) -> dict:
	migrator_class = get_migrator_class(section, company)
	migrator = migrator_class(company)

	try:
		records = migrator.fetch(frappe.parse_json(filters or {}))
	except MigrationError as e:
		log_fetch_failure(migrator, e)
		frappe.throw(
			_("Could not fetch {0} records from the CentHR site: {1}").format(_(migrator.doctype), e),
			title=_("Fetch Failed"),
		)

	return {
		"records": records,
		"count": len(records),
		"running": is_job_enqueued(get_job_id(section, company)),
	}


@frappe.whitelist()
def migrate_records(section: str, company: str, names: str | list) -> int:
	migrator_class = get_migrator_class(section, company)
	frappe.has_permission(migrator_class.doctype, "create", throw=True)

	names = frappe.parse_json(names) if isinstance(names, str) else names
	if not names:
		frappe.throw(_("Select at least one record to migrate"))

	job_id = get_job_id(section, company)
	if is_job_enqueued(job_id):
		frappe.throw(
			_("A migration of these records is already running. Wait for it to finish."),
			title=_("Migration Running"),
		)

	data_log = frappe.get_doc(
		{
			"doctype": DATA_LOG,
			"reference_doctype": migrator_class.doctype,
			"section": section,
			"company": company,
			"total_records": len(names),
		}
	).insert(ignore_permissions=True)

	# A stop requested for an earlier run must not end this one
	frappe.cache.delete_value(get_stop_key(job_id))
	# The job reads the data log, so it must start after the log is committed
	frappe.enqueue(
		RUN_JOB,
		queue="long",
		timeout=60 * 60 * 4,
		job_id=job_id,
		deduplicate=True,
		enqueue_after_commit=True,
		section=section,
		company=company,
		names=names,
		data_log=data_log.name,
	)
	return len(names)


@frappe.whitelist()
def stop_migration(section: str, company: str) -> None:
	get_migrator_class(section, company)
	job_id = get_job_id(section, company)
	if not is_job_enqueued(job_id):
		frappe.throw(_("No migration of these records is running"), title=_("Not Running"))

	# The job checks this between records, so the record being migrated still finishes
	frappe.cache.set_value(get_stop_key(job_id), 1, expires_in_sec=60 * 60 * 4)


def run_migration(section: str, company: str, names: list[str], data_log: str) -> None:
	data_log = start_data_log(data_log)
	stop_key = get_stop_key(get_job_id(section, company))
	stopped = False

	try:
		stopped = not migrate_each(section, company, names, data_log, stop_key)
	except Exception as e:
		frappe.db.rollback()
		data_log.reload()
		add_remaining(data_log, names, frappe._dict(status="Failed", error=get_error_message(e)))
		raise
	finally:
		if stopped:
			add_remaining(data_log, names, frappe._dict(status="Stopped"))
		data_log.set_summary(stopped)
		data_log.completed_on = now_datetime()
		data_log.save(ignore_permissions=True)
		frappe.db.commit()
		frappe.cache.delete_value(stop_key)

	if stopped:
		frappe.publish_realtime(
			STOPPED_EVENT,
			{
				"section": section,
				"names": [row.reference_name for row in data_log.records if row.status == "Stopped"],
				"data_log": data_log.name,
			},
			user=frappe.session.user,
		)


def migrate_each(section: str, company: str, names: list[str], data_log, stop_key: str) -> bool:
	"""Migrate the records one by one. Return False when a stop was requested before the last one."""
	migrator = MIGRATORS[section](company)

	for index, name in enumerate(names, start=1):
		if frappe.cache.get_value(stop_key, expires=True, use_local_cache=False):
			return False

		result = migrator.migrate(name)
		data_log.add_record(name, result, migrator.remote.get(migrator.title_field))
		data_log.save(ignore_permissions=True)
		# Each record is final on its own, so a later failure does not undo it
		frappe.db.commit()
		frappe.publish_realtime(
			PROGRESS_EVENT,
			{
				"section": section,
				"name": name,
				"status": result.status,
				"error": result.error,
				"log": result.log,
				"local_name": result.local_name,
				"data_log": data_log.name,
				"index": index,
				"total": len(names),
			},
			user=frappe.session.user,
		)
	return True


def start_data_log(name: str):
	data_log = frappe.get_doc(DATA_LOG, name)
	data_log.status = "In Progress"
	data_log.started_on = now_datetime()
	data_log.save(ignore_permissions=True)
	frappe.db.commit()
	return data_log


def add_remaining(data_log, names: list[str], result: frappe._dict) -> None:
	"""Record the records that the run did not reach, so the log accounts for every selected record."""
	done = {row.reference_name for row in data_log.records}
	for name in names:
		if name not in done:
			data_log.add_record(name, result)


def get_job_id(section: str, company: str) -> str:
	return f"centhr_migration::{section}::{company}"


def get_stop_key(job_id: str) -> str:
	return f"{job_id}::stop"


def get_migrator_class(section: str, company: str):
	frappe.has_permission(TOOL, "write", throw=True)
	if section not in MIGRATORS:
		frappe.throw(_("Unknown section {0}").format(section))
	if not company:
		frappe.throw(_("Select a Company"))
	frappe.has_permission("Company", "read", doc=company, throw=True)
	return MIGRATORS[section]


def log_fetch_failure(migrator, error: MigrationError) -> None:
	frappe.get_doc(
		{
			"doctype": "CentHR API Logger",
			"doctypes": migrator.doctype,
			"company": migrator.company,
			"status": "Failed",
			"error": str(error),
			**error.log_fields,
		}
	).insert(ignore_permissions=True)
	# The fetch fails with an error next, which would roll the log back
	frappe.db.commit()
