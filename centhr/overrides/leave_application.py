# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from contextlib import contextmanager

import frappe
from frappe import _
from frappe.utils import flt, getdate
from hrms.hr.doctype.leave_application.leave_application import (
	get_employee_leave_approver,
	get_leave_balance_on,
	get_number_of_leave_days,
)
from hrms.hr.doctype.leave_ledger_entry.leave_ledger_entry import create_leave_ledger_entry
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee

from centhr.leave_policy.application import LeaveApplicationPolicy
from centhr.leave_policy.rules import get_rule


class CentHRLeaveApplication:
	"""Applies the leave policy (centhr.leave_policy) and lets the guest web form save a Leave Application.

	HRMS validation checks that the session user may read the employee, which Guest never can.
	The web form has already verified the employee's email OTP in before_insert
	(centhr.api.otp.web_form.validate_web_form_otp), so validate runs as the employee's user.
	"""

	def validate(self):
		policy = LeaveApplicationPolicy(self)
		policy.validate_request()
		if frappe.flags.in_web_form and frappe.session.user == "Guest":
			self.flags.guest_web_form = True
			self.leave_approver = self.leave_approver or get_employee_leave_approver(self.employee)
			with as_employee_user(self.employee):
				super().validate()
		else:
			super().validate()
		policy.validate_leave()

	def before_submit(self):
		LeaveApplicationPolicy(self).validate_approval()

	def validate_dates_across_allocation(self):
		# A leave that runs into the next year is charged to the year it starts in
		if not self.get_overflow_allocation():
			super().validate_dates_across_allocation()

	def validate_balance_leaves(self):
		allocation = self.get_overflow_allocation()
		if not allocation:
			return super().validate_balance_leaves()
		# HRMS would look for balance in the year the leave ends; the policy charges the year it starts
		application = None if self.is_new() else self.name
		self.total_leave_days = get_number_of_leave_days(
			self.employee, self.leave_type, self.from_date, self.to_date, self.half_day, self.half_day_date, leave_application=application
		)
		# The whole leave comes out of that allocation, including the days after its end
		available = flt(
			get_leave_balance_on(
				self.employee,
				self.leave_type,
				self.from_date,
				allocation.to_date,
				consider_all_leaves_in_the_allocation_period=True,
				leave_application=application,
			)
		)
		if self.status != "Rejected" and available < self.total_leave_days:
			frappe.throw(
				_("Insufficient leave balance for {0}: {1} days are left in the allocation this leave starts in.").format(
					self.leave_type, available
				)
			)

	def create_leave_ledger_entry(self, submit=True):
		allocation = self.get_overflow_allocation()
		if not allocation:
			return super().create_leave_ledger_entry(submit)
		if self.status != "Approved" and submit:
			return
		# One entry inside the starting allocation, so next year's credit stays whole
		args = {
			"leaves": self.total_leave_days * -1,
			"from_date": self.from_date,
			"to_date": allocation.to_date,
			"is_lwp": 0,
			"holiday_list": get_holiday_list_for_employee(self.employee, raise_exception=False, as_on=self.from_date) or "",
		}
		create_leave_ledger_entry(self, args, submit)

	def get_overflow_allocation(self):
		"""The allocation this leave starts in, when the policy lets the leave run past its end."""
		rule = get_rule(self.leave_type)
		if not (rule and rule.overflows_year):
			return None
		allocation = frappe.db.get_value(
			"Leave Allocation",
			{
				"employee": self.employee,
				"leave_type": self.leave_type,
				"docstatus": 1,
				"from_date": ["<=", self.from_date],
				"to_date": [">=", self.from_date],
			},
			["name", "to_date"],
			as_dict=True,
		)
		return allocation if allocation and getdate(self.to_date) > getdate(allocation.to_date) else None

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
