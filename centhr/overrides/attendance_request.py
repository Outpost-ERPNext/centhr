# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe


class CentHRAttendanceRequest:
	"""Let the attendance web form save requests for days with no attendance to mark.

	HRMS blocks a request whose every day is a holiday, a leave day or has an unchanged status.
	The web form makes one request per day, so it collects those warnings instead and shows
	them once after saving (centhr.api.web_form.attendance_request.after_insert).
	"""

	def validate_no_attendance_to_create(self):
		if not frappe.flags.in_web_form:
			return super().validate_no_attendance_to_create()

		warnings = frappe.flags.setdefault("attendance_request_warnings", [])
		warnings.extend(warning for warning in self.get_attendance_warnings() if warning["action"] == "Skip")
