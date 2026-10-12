# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator, get_overlap_filters


class LeaveApplicationMigrator(Migrator):
	doctype = "Leave Application"
	list_fields = ("employee", "employee_name", "leave_type", "from_date", "to_date", "status")
	# Same match as the push sync in centhr/api/post/leave_application.py
	duplicate_fields = ("employee", "leave_type", "from_date", "to_date")
	cleared_fields = ("salary_slip",)

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = get_overlap_filters(filters, "from_date", "to_date")
		if filters.status and filters.status != "All":
			remote.append(["status", "=", filters.status])
		return remote


def migrate(company: str, name: str) -> frappe._dict:
	return LeaveApplicationMigrator(company).migrate(name)
