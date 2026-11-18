# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class PmsQuestionTraitMigrator(Migrator):
	doctype = "PMS Question Trait"
	list_fields = ("question_trait",)
	duplicate_fields = ("question_trait",)
	title_field = "question_trait"
	# Shared by every company
	filter_by_company = False


def migrate(company: str, name: str) -> frappe._dict:
	return PmsQuestionTraitMigrator(company).migrate(name)
