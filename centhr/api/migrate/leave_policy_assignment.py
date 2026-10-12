# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator, get_overlap_filters


class LeavePolicyAssignmentMigrator(Migrator):
	"""On submit, HRMS creates the Leave Allocations of the policy here by itself."""

	doctype = "Leave Policy Assignment"
	list_fields = ("employee", "employee_name", "leave_policy", "effective_from", "effective_to", "docstatus")
	duplicate_fields = ("employee", "leave_policy", "effective_from")

	def get_section_filters(self, filters: frappe._dict) -> list:
		return get_overlap_filters(filters, "effective_from", "effective_to")


def migrate(company: str, name: str) -> frappe._dict:
	return LeavePolicyAssignmentMigrator(company).migrate(name)
