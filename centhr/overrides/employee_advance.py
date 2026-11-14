# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.iou import advance, notifications, routing


class CentHREmployeeAdvance:
	"""An Employee Advance is an IOU (centhr.iou). It moves through the Employee Advance Approval workflow:
	line manager (HOD) → Finance 1 → Finance 2, who pays it."""

	def validate(self):
		advance.validate(self)
		routing.route(self)
		super().validate()

	def before_submit(self):
		advance.before_submit(self)
		super().before_submit()

	def on_update(self):
		super().on_update()
		routing.share_with_approvers(self)
		notifications.on_state_change(self)

	def on_submit(self):
		# HRMS's Employee Advance has no on_submit of its own
		if parent := getattr(super(), "on_submit", None):
			parent()
		notifications.on_state_change(self)
