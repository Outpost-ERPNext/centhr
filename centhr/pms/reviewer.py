"""Giving a 360 review: what a reviewer is asked, and submitting their ratings."""

import frappe
from frappe import _
from frappe.utils import today

ALLOCATION = "PMS Form Allocation"
REVIEW = "PMS Question Form"


def get_my_reviews(employee: str) -> list[dict]:
	"""The reviews an employee is asked to give, the ones still to do first."""
	return frappe.get_all(
		ALLOCATION,
		filters={"reviewer": employee, "docstatus": 1},
		fields=[
			"name",
			"reviewee",
			"reviewee_name",
			"department",
			"relationship_type",
			"fiscal_year",
			"quarter",
			"status",
			"review_date",
		],
		order_by="status desc, creation desc",
	)


def get_review_form(allocation: str, employee: str) -> dict:
	"""What a reviewer needs to give one review: who it is about and the questions. A review that was
	given already comes back with its ratings, to read."""
	doc = get_own_allocation(allocation, employee)
	designation = frappe.db.get_value("Employee", doc.reviewee, "designation")
	questions = frappe.get_all(
		"PMS Questionnaire List",
		filters={"parent": doc.form_reference},
		fields=["question", "question_trait"],
		order_by="idx asc",
	)
	given = frappe.db.get_value(REVIEW, {"pms_form_allocation": allocation, "docstatus": 1}, "name")
	answers = frappe.get_doc(REVIEW, given) if given else None
	return {
		"allocation": doc.name,
		"reviewee": doc.reviewee,
		"reviewee_name": doc.reviewee_name,
		"reviewee_designation": designation,
		"department": doc.department,
		"relationship_type": doc.relationship_type,
		"fiscal_year": doc.fiscal_year,
		"quarter": doc.quarter,
		"status": doc.status,
		"review_date": doc.review_date,
		"company_logo": frappe.db.get_value("PMS Settings", doc.company, "company_logo"),
		"questions": questions,
		"ratings": [row.rating for row in answers.pms_questionnaire_list] if answers else [],
		"question_remarks": [row.remarks for row in answers.pms_questionnaire_list] if answers else [],
		"remarks": answers.remarks if answers else None,
	}


def submit_review(allocation: str, employee: str, answers: list[dict], remarks: str | None = None) -> str:
	"""Save and submit the review of one allocation, given by the employee it was asked of."""
	doc = get_own_allocation(allocation, employee)
	if doc.status == "Completed":
		frappe.throw(_("You have submitted this review already."), title=_("Already Reviewed"))

	review = frappe.get_doc(
		{
			"doctype": REVIEW,
			"pms_form_allocation": doc.name,
			"review_date": today(),
			"remarks": remarks,
			"pms_questionnaire_list": [
				# The question text is filled from the questionnaire on save
				{"rating": answer.get("rating"), "remarks": answer.get("remarks")}
				for answer in answers
			],
		}
	)
	# Reviewers have no role on the DocType; this function has checked that the review is theirs
	review.flags.ignore_permissions = True
	review.insert()
	review.submit()
	return review.name


def get_own_allocation(allocation: str, employee: str | None):
	doc = frappe.get_doc(ALLOCATION, allocation)
	if not employee or doc.reviewer != employee or doc.docstatus != 1:
		frappe.throw(_("This review is not asked of you."), frappe.PermissionError)
	return doc
