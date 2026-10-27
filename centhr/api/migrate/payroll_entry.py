# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.base import SAVEPOINT, Migrator, get_overlap_filters
from centhr.api.migrate.client import MigrationError


class PayrollEntryMigrator(Migrator):
	"""Migrate the Salary Slips of the payroll run first.

	The entry is created as a draft, even when it is submitted on CentHR: submitting it here would make
	HRMS create the Salary Slips again. The slips migrated from CentHR are linked to it instead.
	"""

	doctype = "Payroll Entry"
	list_fields = (
		"posting_date",
		"start_date",
		"end_date",
		"payroll_frequency",
		"number_of_employees",
		"docstatus",
	)
	duplicate_fields = ("company", "start_date", "end_date", "posting_date", "payroll_frequency")
	cleared_fields = ("error_message",)
	title_field = "name"

	def get_section_filters(self, filters: frappe._dict) -> list:
		return get_overlap_filters(filters, "start_date", "end_date")

	def create(self, values: dict):
		name = self.remote["name"]
		if frappe.db.exists(self.doctype, name):
			raise MigrationError(
				_("{0} {1} already exists on this site as a different record").format(_(self.doctype), name)
			)

		# Read before creating anything, so a failed request leaves nothing behind
		remote_slips = [
			row["name"]
			for row in self.client.get_all("Salary Slip", [["payroll_entry", "=", name]], ["name"])
		]

		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values})
			doc.insert(ignore_permissions=True, set_name=name)
			self.update_series(name)
			self.link_salary_slips(doc.name, remote_slips)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise

		if self.remote.get("docstatus") == 1:
			self.notes.append(_("Created as draft: submitting it here would create its Salary Slips again"))
		return doc

	def link_salary_slips(self, payroll_entry: str, remote_slips: list[str]) -> None:
		if not remote_slips:
			return

		# Migrated slips keep their CentHR name. payroll_entry is read-only, so it is set directly
		for slip in frappe.get_all(
			"Salary Slip",
			filters={"name": ["in", remote_slips], "payroll_entry": ["is", "not set"]},
			pluck="name",
		):
			frappe.db.set_value("Salary Slip", slip, "payroll_entry", payroll_entry, update_modified=False)

		linked = frappe.db.count(
			"Salary Slip", {"name": ["in", remote_slips], "payroll_entry": payroll_entry}
		)
		self.notes.append(
			_("{0} of its {1} Salary Slips on CentHR are linked to it").format(linked, len(remote_slips))
		)


def migrate(company: str, name: str) -> frappe._dict:
	return PayrollEntryMigrator(company).migrate(name)
