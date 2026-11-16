# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PMSFormAllocation(Document):
	def autoname(self):
		base = f"PMS|{self.fiscal_year}|{self.quarter}|{self.reviewee}|{self.reviewer}"
		# A cancelled allocation keeps its name, so one made again gets a counter
		name, count = base, 0
		while frappe.db.exists(self.doctype, name):
			count += 1
			name = f"{base}|{count}"
		self.name = name

	def validate(self):
		if self.reviewer == self.reviewee:
			frappe.throw(_("An employee does not review themselves."))
		self.set_reviewee_details()
		self.validate_one_per_reviewer()

	def set_reviewee_details(self):
		questionnaire = frappe.db.get_value(
			"PMS Questionnaire", self.form_reference, ["employee", "company", "department"], as_dict=True
		)
		if questionnaire.employee != self.reviewee:
			frappe.throw(_("{0} is not the questionnaire of {1}.").format(self.form_reference, self.reviewee))
		self.company = questionnaire.company
		self.department = questionnaire.department

	def validate_one_per_reviewer(self):
		filters = {
			"reviewer": self.reviewer,
			"form_reference": self.form_reference,
			"docstatus": 1,
			"name": ["!=", self.name],
		}
		if frappe.db.exists(self.doctype, filters):
			frappe.throw(_("{0} already reviews {1} this quarter.").format(self.reviewer, self.reviewee))
