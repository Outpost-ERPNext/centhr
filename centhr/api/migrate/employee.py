# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _

from centhr.api.migrate.base import Migrator
from centhr.api.migrate.employee_map import get_local_employees


class EmployeeMigrator(Migrator):
	doctype = "Employee"
	list_fields = ("employee_number", "employee_name", "status", "company", "department", "date_of_joining")
	duplicate_fields = ("employee_number",)
	# "employee" holds the name on the CentHR site; lft, rgt and old_parent are rebuilt here
	cleared_fields = ("employee", "lft", "rgt", "old_parent")
	# Payroll fields that centhr made mandatory; employees created before that have them empty
	optional_fields = ("salary_structure", "employee_base", "from_date", "payroll_payable_account")
	copied_masters = (
		"Department",
		"Designation",
		"Employment Type",
		"Employee Grade",
		"Territory",
		"Channel",
		"Holiday List",
		"Shift Type",
		"Employee Health Insurance",
		"Branch",
	)

	def get_section_filters(self, filters: frappe._dict) -> list:
		if filters.status == "Active":
			return [["status", "=", "Active"]]
		if filters.status == "Inactive":
			return [["status", "!=", "Active"]]
		return []

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		numbers = {row["name"]: row.get("employee_number") or row["name"] for row in rows}
		local_names = get_local_employees(list(numbers.values()))
		return {name: local_names[number] for name, number in numbers.items() if number in local_names}

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		values["employee_number"] = remote.get("employee_number") or remote["name"]
		self.keep_first_phone(values)
		self.clean_emails(values)
		return values

	def clean_emails(self, values: dict) -> None:
		"""Remove angle brackets, plain or HTML-escaped, that the CentHR site kept around an address."""
		for df in self.meta.fields:
			value = values.get(df.fieldname)
			if df.options != "Email" or not value:
				continue
			cleaned = re.sub(r"&(amp;)*[lg]t;|[<>]", "", value).strip()
			if cleaned != value:
				values[df.fieldname] = cleaned
				self.notes.append(_("{0} {1} cleaned to {2}").format(_(df.label), value, cleaned))

	def keep_first_phone(self, values: dict) -> None:
		"""The CentHR site accepts several numbers in one phone field; this site accepts one."""
		for df in self.meta.fields:
			value = values.get(df.fieldname)
			if df.options != "Phone" or not value or not re.search(r"[,;/]", value):
				continue
			first = re.split(r"[,;/]", value)[0].strip()
			values[df.fieldname] = first
			self.notes.append(_("{0} had several numbers ({1}), kept {2}").format(_(df.label), value, first))

	def find_existing(self, values: dict) -> str | None:
		return get_local_employees([values["employee_number"]]).get(values["employee_number"])


def migrate(company: str, name: str) -> frappe._dict:
	return EmployeeMigrator(company).migrate(name)
