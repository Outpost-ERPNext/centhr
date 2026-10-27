# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class SalaryComponentMigrator(Migrator):
	doctype = "Salary Component"
	list_fields = ("salary_component", "salary_component_abbr", "type", "disabled")
	duplicate_fields = ("salary_component",)
	title_field = "salary_component"
	# Salary Component has no company field
	filter_by_company = False


def migrate(company: str, name: str) -> frappe._dict:
	return SalaryComponentMigrator(company).migrate(name)
