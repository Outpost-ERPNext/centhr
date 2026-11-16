# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today

from centhr.centhr.doctype.pms_360_degree.pms_360_degree import get_department_review
from centhr.pms.scoring import MAX_RATING, average_rating, rating_score

ALLOCATION = "PMS Form Allocation"
COPIED_FIELDS = (
	"reviewer",
	"reviewee",
	"relationship_type",
	"fiscal_year",
	"quarter",
	"company",
	"department",
)


class PMSQuestionForm(Document):
	def autoname(self):
		base = f"PMS-R|{self.fiscal_year}|{self.quarter}|{self.reviewee}|{self.reviewer}"
		name, count = base, 0
		while frappe.db.exists(self.doctype, name):
			count += 1
			name = f"{base}|{count}"
		self.name = name

	def before_naming(self):
		# The name is made of what the allocation says
		self.set_from_allocation()

	def validate(self):
		# A review migrated from the CentHR site keeps the scores and weights it was given there
		if frappe.flags.centhr_migration:
			return
		self.set_from_allocation()
		self.validate_one_per_allocation()
		self.validate_ratings()
		self.set_weights()
		self.calculate_score()
		self.review_date = self.review_date or today()

	def set_from_allocation(self):
		if frappe.flags.centhr_migration:
			return
		allocation = frappe.db.get_value(
			ALLOCATION,
			self.pms_form_allocation,
			[*COPIED_FIELDS, "form_reference", "docstatus"],
			as_dict=True,
		)
		if allocation.docstatus != 1:
			frappe.throw(_("This review is no longer asked for."), title=_("Allocation Cancelled"))
		for field in COPIED_FIELDS:
			self.set(field, allocation[field])
		self.pms_questionnaire = allocation.form_reference

	def validate_one_per_allocation(self):
		filters = {"pms_form_allocation": self.pms_form_allocation, "docstatus": 1, "name": ["!=", self.name]}
		if frappe.db.exists(self.doctype, filters):
			frappe.throw(_("This review has been submitted already."), title=_("Already Reviewed"))

	def validate_ratings(self):
		"""Every question of the questionnaire is rated, in whole points from 1 to 5."""
		questions = frappe.get_all(
			"PMS Questionnaire List",
			filters={"parent": self.pms_questionnaire},
			pluck="question",
			order_by="idx asc",
		)
		if len(questions) != len(self.pms_questionnaire_list):
			frappe.throw(_("Rate every question of the questionnaire."))
		for row, question in zip(self.pms_questionnaire_list, questions, strict=True):
			row.question = question
			if flt(row.rating) not in range(1, MAX_RATING + 1):
				frappe.throw(_("Question {0}: choose a rating from 1 to {1}.").format(row.idx, MAX_RATING))

	def set_weights(self):
		review = get_department_review(self.company, self.department, self.fiscal_year, self.quarter)
		if not review:
			frappe.throw(
				_("{0} is not part of the 360 review of {1} {2}.").format(
					self.department, self.quarter, self.fiscal_year
				)
			)
		self.superior_weight = review.superior_weight
		self.peers_weight = review.peers_weight

	def calculate_score(self):
		self.average_rating = average_rating([flt(row.rating) for row in self.pms_questionnaire_list])
		self.rating_score = rating_score(self.average_rating, self.weight)

	@property
	def weight(self) -> float:
		"""The weight of this reviewer's kind: a peer's, or the line manager's."""
		return flt(self.peers_weight if self.relationship_type == "Peers" else self.superior_weight)

	def on_submit(self):
		self.set_allocation_status("Completed", self.review_date)

	def on_cancel(self):
		self.set_allocation_status("Pending", None)

	def set_allocation_status(self, status: str, review_date) -> None:
		if frappe.flags.centhr_migration:
			return
		frappe.db.set_value(
			ALLOCATION, self.pms_form_allocation, {"status": status, "review_date": review_date}
		)
