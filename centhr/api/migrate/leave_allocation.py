# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator, get_overlap_filters


class LeaveAllocationMigrator(Migrator):
	doctype = "Leave Allocation"
	list_fields = ("employee", "employee_name", "leave_type", "from_date", "to_date", "new_leaves_allocated")
	duplicate_fields = ("employee", "leave_type", "from_date", "to_date")
	# The schedule is rebuilt on submit. leave_policy is fetched from the assignment, and the same
	# policy name can be another company's policy here
	cleared_fields = ("leave_policy_assignment", "leave_policy", "compensatory_request", "earned_leave_schedule")

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = get_overlap_filters(filters, "from_date", "to_date")
		if filters.leave_type:
			remote.append(["leave_type", "=", filters.leave_type])
		return remote


def migrate(company: str, name: str) -> frappe._dict:
	return LeaveAllocationMigrator(company).migrate(name)
