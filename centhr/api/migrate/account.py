# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.tree import TreeMigrator


class AccountMigrator(TreeMigrator):
	doctype = "Account"
	list_fields = (
		"account_name",
		"account_number",
		"company",
		"parent_account",
		"root_type",
		"account_type",
		"is_group",
	)
	duplicate_fields = ("account_name", "company")
	title_field = "account_name"
	parent_field = "parent_account"

	def get_section_filters(self, filters: frappe._dict) -> list:
		if filters.root_type and filters.root_type != "All":
			return [["root_type", "=", filters.root_type]]
		return []

	def get_root_filters(self) -> dict:
		return {"root_type": self.remote.get("root_type")}


def migrate(company: str, name: str) -> frappe._dict:
	return AccountMigrator(company).migrate(name)
