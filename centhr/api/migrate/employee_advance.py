# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from centhr.api.migrate.base import Migrator


class EmployeeAdvanceMigrator(Migrator):
	"""The Employee and the advance Account must be migrated first.

	The paid, claimed and returned amounts are copied from the CentHR site, so the status matches there.
	Migrate the Payment Entry of the advance next, in the Payment Entry tab, to book the payment here.
	"""

	doctype = "Employee Advance"
	list_fields = (
		"employee",
		"employee_name",
		"posting_date",
		"advance_amount",
		"paid_amount",
		"status",
		"docstatus",
	)
	duplicate_fields = ("employee", "posting_date", "advance_amount", "purpose")
	# A new record must start in the first workflow state; submitting it sets "Approved".
	# The line manager is set again from this site's employee.
	cleared_fields = ("workflow_state", "line_manager")

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = []
		if filters.from_date:
			remote.append(["posting_date", ">=", filters.from_date])
		if filters.to_date:
			remote.append(["posting_date", "<=", filters.to_date])
		if filters.status and filters.status != "All":
			remote.append(["status", "=", filters.status])
		return remote

	def find_existing(self, values: dict) -> str | None:
		"""Employees sometimes submit the same request many times; a submitted advance never matches a draft copy."""
		filters = {fieldname: values.get(fieldname) for fieldname in self.duplicate_fields}
		filters["docstatus"] = self.remote.get("docstatus") or 0
		return frappe.db.get_value(self.doctype, filters, "name")

	def create(self, values: dict):
		doc = super().create(values)
		if flt(doc.paid_amount):
			self.notes.append(
				_("Migrate the Payment Entry of this advance next, so the paid amount has a ledger entry here")
			)
		return doc


def migrate(company: str, name: str) -> frappe._dict:
	return EmployeeAdvanceMigrator(company).migrate(name)
