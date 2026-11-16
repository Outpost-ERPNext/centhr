# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PMSQuestion(Document):
	def validate(self):
		# A general question is asked for everyone, so a leftover scope would only mislead
		if self.is_a_general_question:
			self.department = None
			self.designation = None
