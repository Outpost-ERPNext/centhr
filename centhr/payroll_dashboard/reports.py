"""Reports tab: the HR and payroll reports the user may open, by category."""

import frappe
from frappe import _

# Category of a report by the DocType it reports on
CATEGORIES = {
	_("Payroll"): ["Salary Slip", "Payroll Entry", "Salary Structure Assignment", "Additional Salary", "Salary Withholding"],
	_("Attendance"): ["Attendance", "Employee Checkin", "Shift Assignment", "Shift Type", "Attendance Request"],
	_("Leaves"): ["Leave Application", "Leave Allocation", "Leave Ledger Entry"],
	_("HR & Staff"): ["Employee", "Department", "Designation", "Employee Grade", "Employee Separation", "Employee Onboarding"],
	_("Advances"): ["Employee Advance", "Expense Claim", "Gratuity", "Loan"],
}


def get_reports() -> list[dict]:
	category_of = {doctype: category for category, doctypes in CATEGORIES.items() for doctype in doctypes}
	reports = frappe.get_all(
		"Report",
		filters={"disabled": 0, "ref_doctype": ["in", list(category_of)]},
		fields=["name", "ref_doctype", "report_type", "module"],
		order_by="name asc",
	)
	allowed = set(frappe.get_user().get_all_reports())
	return [
		{**r, "category": category_of[r.ref_doctype], "route": report_route(r)}
		for r in reports
		if r.name in allowed and frappe.has_permission(r.ref_doctype, "report")
	]


def report_route(report) -> str:
	"""Desk opens script and query reports on their own page, report builder ones on the list's report view."""
	if report.report_type == "Report Builder":
		return f"/desk/{frappe.scrub(report.ref_doctype).replace('_', '-')}/view/report/{report.name}"
	return f"/desk/query-report/{report.name}"
