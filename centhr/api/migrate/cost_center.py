# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.tree import TreeMigrator


class CostCenterMigrator(TreeMigrator):
	doctype = "Cost Center"
	list_fields = (
		"cost_center_name",
		"cost_center_number",
		"company",
		"parent_cost_center",
		"is_group",
		"disabled",
	)
	duplicate_fields = ("cost_center_name", "company")
	title_field = "cost_center_name"
	parent_field = "parent_cost_center"


def migrate(company: str, name: str) -> frappe._dict:
	return CostCenterMigrator(company).migrate(name)
