# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CentHrSettings(Document):
	def validate(self):
		self.validate_iou_approvers()

	def validate_iou_approvers(self):
		# SOP: the Finance user who approves an IOU cannot also approve its payment
		if self.iou_finance_1 and self.iou_finance_1 == self.iou_finance_2:
			frappe.throw(_("Finance 1 and Finance 2 must be different users."), title=_("IOU Approvers"))

		seen = set()
		for row in self.iou_proxies:
			if row.approver == row.proxy:
				frappe.throw(_("Row {0}: an approver cannot be their own proxy.").format(row.idx))
			if row.approver in seen:
				frappe.throw(_("Row {0}: {1} already has a proxy.").format(row.idx, row.approver))
			seen.add(row.approver)
