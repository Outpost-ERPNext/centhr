# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import today


class PMSQuestionnaire(Document):
	def autoname(self):
		# One per employee and quarter
		self.name = f"PMS-{self.fiscal_year}-{self.quarter}-{self.employee}"

	def validate(self):
		self.set_employee_details()
		self.validate_questions()
		self.validate_closed()
		self.posting_date = self.posting_date or today()

	def set_employee_details(self):
		"""The department the employee is reviewed in stays as it was when the questionnaire was made."""
		employee = frappe.db.get_value("Employee", self.employee, ["company", "department"], as_dict=True)
		self.company = employee.company
		self.department = self.department or employee.department

	def validate_questions(self):
		questions = [(row.question or "").strip() for row in self.pms_questionnaire_list]
		if len(questions) != len(set(questions)):
			frappe.throw(_("The same question is listed twice."))
		if self.status == "Completed" and not questions:
			frappe.throw(_("A questionnaire needs at least one question before it is closed."))

	def validate_closed(self):
		"""The reviewers answer the questions as they were when the questionnaire was closed."""
		if self.is_new() or frappe.db.get_value(self.doctype, self.name, "status") != "Completed":
			return
		before = frappe.get_all(
			"PMS Questionnaire List", filters={"parent": self.name}, pluck="question", order_by="idx asc"
		)
		if self.status == "Completed" and before != [row.question for row in self.pms_questionnaire_list]:
			frappe.throw(
				_("This questionnaire is closed. Reopen it to change its questions."), title=_("Closed")
			)
