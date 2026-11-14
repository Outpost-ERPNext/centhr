# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.iou import claim, notifications, routing


class CentHRExpenseClaim:
	"""An Expense Claim settles the employee's open IOU, or claims expenses paid from pocket (centhr.iou).
	It moves through the Expense Claim Approval workflow: line manager (HOD) → Finance 1."""

	def validate(self):
		routing.route(self)
		claim.validate(self)
		super().validate()

	def validate_employee_scope(self):
		"""HRMS lets only the employee or HR save a claim. The approver of the current step saves it too,
		when the workflow moves it on."""
		previous = self.get_doc_before_save()
		acting = previous and frappe.session.user in (previous.get("current_approver"), previous.get("proxy_approver"))
		if not acting:
			return super().validate_employee_scope()

		ignore_permissions = self.flags.ignore_permissions
		self.flags.ignore_permissions = True
		try:
			super().validate_employee_scope()
		finally:
			self.flags.ignore_permissions = ignore_permissions

	def before_submit(self):
		claim.before_submit(self)
		super().before_submit()

	def on_update(self):
		super().on_update()
		routing.share_with_approvers(self)
		notifications.on_state_change(self)

	def on_submit(self):
		super().on_submit()
		notifications.on_state_change(self)
