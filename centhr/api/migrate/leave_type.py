# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class LeaveTypeMigrator(Migrator):
	doctype = "Leave Type"
	list_fields = ("leave_type_name", "max_leaves_allowed", "is_lwp", "is_carry_forward", "is_earned_leave")
	duplicate_fields = ("leave_type_name",)
	title_field = "leave_type_name"
	# Leave Type has no company field
	filter_by_company = False


def migrate(company: str, name: str) -> frappe._dict:
	return LeaveTypeMigrator(company).migrate(name)
