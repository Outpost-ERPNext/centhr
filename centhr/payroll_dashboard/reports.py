"""Reports tab: the HR and payroll reports the user may open, by category."""

import frappe
from frappe import _

OTHER = "Other"
# Category of a report by the DocType it reports on
CATEGORIES = {
	"Payroll": [
		"Salary Slip",
		"Payroll Entry",
		"Salary Structure",
		"Salary Structure Assignment",
		"Additional Salary",
		"Salary Withholding",
		"Statutory Obligation",
		"Payroll Master Sheet",
		"Payment Request Form",
	],
	"Attendance": ["Attendance", "Employee Checkin", "Shift Assignment", "Shift Type", "Attendance Request"],
	"Leaves": ["Leave Application", "Leave Allocation", "Leave Ledger Entry"],
	"HR & Staff": [
		"Employee",
		"Department",
		"Designation",
		"Employee Grade",
		"Employee Separation",
		"Employee Onboarding",
	],
	"Advances": ["Employee Advance", "Expense Claim", "Gratuity", "Loan", "IOU and Loans"],
}
# A report on any other DocType belongs here when its module, or its DocType's, is one of these
MODULES = ("HR", "Payroll", "centhr")
# Category of such a report by a word in its name; the first match wins
KEYWORDS = {
	"Attendance": ("attendance", "checkin", "shift"),
	"Leaves": ("leave",),
	"Advances": ("advance", "iou", "loan", "expense", "claim"),
	"Payroll": ("salary", "payroll", "pay ", "tax", "deduction", "pension", "statutory", "bank"),
	"HR & Staff": ("employee", "staff", "recruit", "appraisal", "headcount"),
}


def get_reports() -> list[dict]:
	"""Enabled reports on an HR or payroll DocType, or of an HR, payroll or CentHR module, that the
	user has the role for and may run on its DocType. A new custom report shows up by itself."""
	category_of = {doctype: category for category, doctypes in CATEGORIES.items() for doctype in doctypes}
	in_module = frappe.get_all("DocType", filters={"module": ["in", MODULES]}, pluck="name")
	reports = frappe.get_all(
		"Report",
		filters={"disabled": 0},
		or_filters=[["ref_doctype", "in", [*category_of, *in_module]], ["module", "in", MODULES]],
		fields=["name", "ref_doctype", "report_type", "module"],
		order_by="name asc",
	)
	allowed = set(frappe.get_user().get_all_reports())
	return [
		{**r, "category": _(category_of.get(r.ref_doctype) or categorize(r.name)), "route": report_route(r)}
		for r in reports
		if r.name in allowed and frappe.has_permission(r.ref_doctype, "report")
	]


def categorize(report_name: str) -> str:
	name = report_name.lower()
	return next(
		(category for category, words in KEYWORDS.items() if any(word in name for word in words)), OTHER
	)


def report_route(report) -> str:
	"""Desk opens script and query reports on their own page, report builder ones on the list's report view."""
	if report.report_type == "Report Builder":
		return f"/desk/{frappe.scrub(report.ref_doctype).replace('_', '-')}/view/report/{report.name}"
	return f"/desk/query-report/{report.name}"
