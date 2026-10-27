# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class AdditionalSalaryMigrator(Migrator):
	"""Its Salary Component and the employee's Salary Structure Assignment must be migrated first."""

	doctype = "Additional Salary"
	list_fields = (
		"employee",
		"employee_name",
		"salary_component",
		"amount",
		"payroll_date",
		"is_recurring",
		"docstatus",
	)
	# Recurring records have no payroll_date, so Fetch shows them as Pending; find_existing still matches them
	duplicate_fields = ("employee", "salary_component", "amount", "payroll_date")
	# The Employee Referral or Employee Advance that created the record is not migrated
	cleared_fields = ("ref_doctype", "ref_docname")

	def get_section_filters(self, filters: frappe._dict) -> list:
		if filters.salary_component:
			return [["salary_component", "=", filters.salary_component]]
		return []

	def find_existing(self, values: dict) -> str | None:
		date_field = "from_date" if values.get("is_recurring") else "payroll_date"
		filters = {
			fieldname: values.get(fieldname)
			for fieldname in ("employee", "salary_component", "amount", date_field)
		}
		return frappe.db.get_value(self.doctype, {**filters, "docstatus": ["!=", 2]}, "name")


def migrate(company: str, name: str) -> frappe._dict:
	return AdditionalSalaryMigrator(company).migrate(name)
