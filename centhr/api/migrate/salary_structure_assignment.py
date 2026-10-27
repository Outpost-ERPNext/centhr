# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator
from centhr.api.migrate.salary_structure import StructureMap


class SalaryStructureAssignmentMigrator(Migrator):
	"""Its Salary Structure must be migrated (and submitted) first."""

	doctype = "Salary Structure Assignment"
	list_fields = ("employee", "employee_name", "salary_structure", "from_date", "base", "docstatus")
	# HRMS allows one assignment per employee and from date
	duplicate_fields = ("employee", "salary_structure", "from_date")

	def __init__(self, company: str):
		super().__init__(company)
		self.structures = StructureMap(company)

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = []
		if filters.from_date:
			remote.append(["from_date", ">=", filters.from_date])
		if filters.to_date:
			remote.append(["from_date", "<=", filters.to_date])
		return remote

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		self.structures.load([row.get("salary_structure") for row in rows])
		return super().get_existing_names(rows)

	def get_key(self, row: dict) -> tuple | None:
		return super().get_key(
			{**row, "salary_structure": self.structures.get_local(row.get("salary_structure"))}
		)

	def get_local_link(self, doctype: str, value: str) -> str | None:
		if doctype == "Salary Structure":
			# Another company's structure can have the same name here, so never match by name alone
			return self.structures.get_local_or_throw(value)
		return super().get_local_link(doctype, value)


def migrate(company: str, name: str) -> frappe._dict:
	return SalaryStructureAssignmentMigrator(company).migrate(name)
