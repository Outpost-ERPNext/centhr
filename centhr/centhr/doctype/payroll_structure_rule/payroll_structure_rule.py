# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# The batches every company has; a confidential batch needs its own name
RESERVED_BATCHES = ("Regular", "Exited")


class PayrollStructureRule(Document):
	def validate(self):
		self.company = frappe.db.get_value("Salary Structure", self.salary_structure, "company")
		if self.confidential:
			self.validate_batch()
		else:
			self.allowed_role = self.batch_name = None

	def validate_batch(self):
		self.batch_name = (self.batch_name or "").strip()
		if not self.allowed_role or not self.batch_name:
			frappe.throw(_("A confidential salary structure needs an allowed role and a payroll batch."))
		if self.batch_name in RESERVED_BATCHES:
			frappe.throw(
				_("{0} is the name of a standard batch. Give the confidential batch its own name.").format(
					self.batch_name
				)
			)
