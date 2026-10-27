# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, fmt_money

from centhr.api.migrate.base import Migrator, get_overlap_filters
from centhr.api.migrate.salary_structure import StructureMap


class SalarySlipMigrator(Migrator):
	"""The employee's Salary Structure Assignment must be migrated first.

	Migrate slips before their Payroll Entry: the Payroll Entry tab creates the entry as a draft and links
	the slips migrated here to it, so HRMS never creates the slips a second time.
	"""

	doctype = "Salary Slip"
	list_fields = ("employee", "employee_name", "start_date", "end_date", "net_pay", "docstatus")
	# HRMS allows one slip per employee and period (check_existing)
	duplicate_fields = ("employee", "start_date", "end_date")
	# Journal Entries and Timesheets are not migrated
	cleared_fields = ("journal_entry", "timesheets")

	def __init__(self, company: str):
		super().__init__(company)
		self.structures = StructureMap(company)

	def get_section_filters(self, filters: frappe._dict) -> list:
		return get_overlap_filters(filters, "start_date", "end_date")

	def get_local_link(self, doctype: str, value: str) -> str | None:
		if doctype == "Salary Structure":
			# Another company's structure can have the same name here, so never match by name alone
			return self.structures.get_local_or_throw(value)
		return super().get_local_link(doctype, value)

	def create(self, values: dict):
		# CentHR emailed the slip to the employee already. HRMS skips the email for slips of a payroll run
		frappe.flags.via_payroll_entry = True
		try:
			doc = super().create(values)
		finally:
			frappe.flags.via_payroll_entry = False

		# HRMS calculates the slip again from the structure and attendance here
		remote_net_pay = flt(self.remote.get("net_pay"))
		if flt(doc.net_pay) != remote_net_pay:
			self.notes.append(
				_("Net pay here is {0}, on CentHR {1}").format(
					fmt_money(doc.net_pay, currency=doc.currency),
					fmt_money(remote_net_pay, currency=doc.currency),
				)
			)
		return doc


def migrate(company: str, name: str) -> frappe._dict:
	return SalarySlipMigrator(company).migrate(name)
