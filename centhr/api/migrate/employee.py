# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator
from centhr.api.migrate.employee_map import get_local_employees


class EmployeeMigrator(Migrator):
	doctype = "Employee"
	list_fields = ("employee_number", "employee_name", "status", "company", "department", "date_of_joining")
	duplicate_fields = ("employee_number",)
	# "employee" holds the name on the CentHR site; lft, rgt and old_parent are rebuilt here
	cleared_fields = ("employee", "lft", "rgt", "old_parent")

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
		return values

	def find_existing(self, values: dict) -> str | None:
		return get_local_employees([values["employee_number"]]).get(values["employee_number"])


def migrate(company: str, name: str) -> frappe._dict:
	return EmployeeMigrator(company).migrate(name)
