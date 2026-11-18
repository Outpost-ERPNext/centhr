# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class KpiUomMigrator(Migrator):
	doctype = "KPI UOM"
	list_fields = ("name1",)
	duplicate_fields = ("name1",)
	title_field = "name1"
	# Shared by every company
	filter_by_company = False


def migrate(company: str, name: str) -> frappe._dict:
	return KpiUomMigrator(company).migrate(name)
