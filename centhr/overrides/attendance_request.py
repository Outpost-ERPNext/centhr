# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.share import add_docshare


class CentHRAttendanceRequest:
	"""Routes the request to the employee's line manager, and lets the attendance web form save
	requests for days with no attendance to mark.

	HRMS blocks a request whose every day is a holiday, a leave day or has an unchanged status.
	The web form makes one request per day, so it collects those warnings instead and shows
	them once after saving (centhr.api.web_form.attendance_request.after_insert).
	"""

	def validate(self):
		if self.docstatus == 0:
			self.line_manager = get_line_manager(self.employee)
		super().validate()

	def on_update(self):
		super().on_update()
		self.share_with_line_manager()

	def share_with_line_manager(self):
		"""Line managers usually have only the Employee role, which cannot submit an Attendance Request.
		A share lets them open and approve (submit) this one request, and notifies them."""
		if self.docstatus != 0 or not self.line_manager or self.line_manager == frappe.session.user:
			return
		add_docshare(
			self.doctype,
			self.name,
			self.line_manager,
			read=1,
			write=1,
			submit=1,
			notify=1,
			flags={"ignore_share_permission": True},
		)

	def validate_no_attendance_to_create(self):
		if not frappe.flags.in_web_form:
			return super().validate_no_attendance_to_create()

		warnings = frappe.flags.setdefault("attendance_request_warnings", [])
		warnings.extend(warning for warning in self.get_attendance_warnings() if warning["action"] == "Skip")


def get_line_manager(employee: str) -> str | None:
	"""The user of the employee's Reports To manager."""
	manager = frappe.db.get_value("Employee", employee, "reports_to")
	return frappe.db.get_value("Employee", manager, "user_id") if manager else None
