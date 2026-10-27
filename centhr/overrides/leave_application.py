# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from contextlib import contextmanager

import frappe
from hrms.hr.doctype.leave_application.leave_application import get_employee_leave_approver


class CentHRLeaveApplication:
	"""Let the guest leave-application web form save a Leave Application.

	HRMS validation checks that the session user may read the employee, which Guest never can.
	The web form has already verified the employee's email OTP in before_insert
	(centhr.api.otp.web_form.validate_web_form_otp), so validate runs as the employee's user.
	"""

	def validate(self):
		if not (frappe.flags.in_web_form and frappe.session.user == "Guest"):
			return super().validate()

		self.flags.guest_web_form = True
		self.leave_approver = self.leave_approver or get_employee_leave_approver(self.employee)
		with as_employee_user(self.employee):
			super().validate()

	def validate_leave_approver(self):
		# The web form saves without an approver when neither the Employee nor the Department has one
		if self.flags.guest_web_form and not self.leave_approver:
			return
		super().validate_leave_approver()


@contextmanager
def as_employee_user(employee: str):
	"""Run as the employee's user, or Administrator if they have none.

	Not frappe.set_user: it also clears form_dict and the session data in the middle of the request.
	"""
	user = frappe.db.get_value("Employee", employee, "user_id")
	if not user or not frappe.db.get_value("User", user, "enabled"):
		user = "Administrator"

	session_user = frappe.session.user
	frappe.local.session.user = user
	frappe.local.user_perms = None
	try:
		yield
	finally:
		frappe.local.session.user = session_user
		frappe.local.user_perms = None
