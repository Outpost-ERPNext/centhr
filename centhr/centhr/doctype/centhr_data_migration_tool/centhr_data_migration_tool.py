# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.background_jobs import is_job_enqueued

from centhr.api.migrate.attendance import AttendanceMigrator
from centhr.api.migrate.base import get_error_message
from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.employee import EmployeeMigrator
from centhr.api.migrate.leave_allocation import LeaveAllocationMigrator
from centhr.api.migrate.leave_application import LeaveApplicationMigrator
from centhr.api.migrate.leave_policy_assignment import LeavePolicyAssignmentMigrator
from centhr.api.migrate.leave_type import LeaveTypeMigrator

TOOL = "Centhr Data Migration Tool"
DATA_LOG = "Centhr Data Log"
RUN_JOB = "centhr.centhr.doctype.centhr_data_migration_tool.centhr_data_migration_tool.run_migration"
PROGRESS_EVENT = "centhr_migration_progress"
MIGRATORS = {
	"employee": EmployeeMigrator,
	"leave_type": LeaveTypeMigrator,
	"leave_policy_assignment": LeavePolicyAssignmentMigrator,
	"leave_allocation": LeaveAllocationMigrator,
	"leave_application": LeaveApplicationMigrator,
	"attendance": AttendanceMigrator,
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

	return {"records": records, "count": len(records)}


@frappe.whitelist()
def migrate_records(section: str, company: str, names: str | list) -> int:
	migrator_class = get_migrator_class(section, company)
	frappe.has_permission(migrator_class.doctype, "create", throw=True)

	names = frappe.parse_json(names) if isinstance(names, str) else names
	if not names:
		frappe.throw(_("Select at least one record to migrate"))

	job_id = f"centhr_migration::{section}::{company}"
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


def run_migration(section: str, company: str, names: list[str], data_log: str) -> None:
	data_log = start_data_log(data_log)

	try:
		migrate_each(section, company, names, data_log)
	except Exception as e:
		frappe.db.rollback()
		data_log.reload()
		fail_remaining(data_log, names, e)
		raise
	finally:
		data_log.set_summary()
		data_log.completed_on = now_datetime()
		data_log.save(ignore_permissions=True)
		frappe.db.commit()


def migrate_each(section: str, company: str, names: list[str], data_log) -> None:
	migrator = MIGRATORS[section](company)

	for index, name in enumerate(names, start=1):
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


def start_data_log(name: str):
	data_log = frappe.get_doc(DATA_LOG, name)
	data_log.status = "In Progress"
	data_log.started_on = now_datetime()
	data_log.save(ignore_permissions=True)
	frappe.db.commit()
	return data_log


def fail_remaining(data_log, names: list[str], error: Exception) -> None:
	"""Record the records that the run did not reach, so the log accounts for every selected record."""
	done = {row.reference_name for row in data_log.records}
	result = frappe._dict(status="Failed", error=get_error_message(error))
	for name in names:
		if name not in done:
			data_log.add_record(name, result)


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
