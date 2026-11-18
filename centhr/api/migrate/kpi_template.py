# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.pms_base import PmsMigrator


class KpiTemplateMigrator(PmsMigrator):
	"""Its KPI UOMs must be migrated first. A submitted template is submitted here without creating
	a KPI Result: the results are migrated in the KPI Result tab."""

	doctype = "KPI Template"
	list_fields = ("employee", "employee_name", "fiscal_year", "month", "department", "docstatus")
	duplicate_fields = ("employee", "fiscal_year", "month")
	remote_filter_fields = ("fiscal_year", "month")

	def get_section_filters(self, filters: frappe._dict) -> list:
		# A department's master template has no employee; it only served to make the employees' templates
		return [["employee", "is", "set"], *super().get_section_filters(filters)]


def migrate(company: str, name: str) -> frappe._dict:
	return KpiTemplateMigrator(company).migrate(name)
