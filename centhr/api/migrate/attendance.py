# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.base import Migrator


class AttendanceMigrator(Migrator):
	doctype = "Attendance"
	list_fields = ("employee", "employee_name", "attendance_date", "status")
	# Same match as the push sync in centhr/api/post/attendance.py
	duplicate_fields = ("employee", "attendance_date")
	cleared_fields = ("leave_application", "attendance_request")

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = []
		if filters.from_date:
			remote.append(["attendance_date", ">=", filters.from_date])
		if filters.to_date:
			remote.append(["attendance_date", "<=", filters.to_date])
		if filters.status and filters.status != "All":
			remote.append(["status", "=", filters.status])
		return remote


def migrate(company: str, name: str) -> frappe._dict:
	return AttendanceMigrator(company).migrate(name)
