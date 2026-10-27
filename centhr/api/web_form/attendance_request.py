# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Attendance regularization from the `attendance` web form.

The web form saves one Attendance Request and sends `employee_code_confirmation` and
`request_dates` (one row per day, each with its own reason) with the form data. Attendance
Request has no fields for them, so they are read from the request here. The submitted
request becomes the first day, and `after_insert` creates one more request for each other day.
"""

import json

import frappe
from frappe import _
from frappe.utils import format_date, getdate

REASONS = ("Work From Home", "On Duty")
MAX_DAYS = 31


def before_insert(doc, method=None):
	# The requests made in after_insert also run this hook while the web form is saving
	if not frappe.flags.in_web_form or doc.flags.extra_day:
		return

	frappe.flags.attendance_request_warnings = []
	data = get_submitted_data()
	validate_employee(doc, (data.get("employee_code_confirmation") or "").strip())
	days = get_request_days(doc, data.get("request_dates"))

	first = days[0]
	doc.from_date = doc.to_date = first["request_date"]
	doc.reason = first["reason"]
	doc.explanation = first["explanation"]
	doc.flags.extra_days = days[1:]


def after_insert(doc, method=None):
	if doc.flags.extra_days is None:
		return

	for day in doc.flags.extra_days:
		request = frappe.get_doc(
			{
				"doctype": "Attendance Request",
				"employee": doc.employee,
				"company": doc.company,
				"from_date": day["request_date"],
				"to_date": day["request_date"],
				"reason": day["reason"],
				"explanation": day["explanation"],
			}
		)
		request.flags.extra_day = True
		request.insert(ignore_permissions=True)

	show_attendance_warnings()


def show_attendance_warnings() -> None:
	# Days HRMS would have refused; the requests are saved and the user is told what gets skipped
	warnings = frappe.flags.pop("attendance_request_warnings", None)
	if not warnings:
		return

	message_table = [[_("Date"), _("Reason"), _("Action")]]
	for warning in sorted(warnings, key=lambda warning: getdate(warning["date"])):
		message_table.append([format_date(warning["date"]), _(warning["reason"]), _(warning["action"])])

	frappe.msgprint(
		title=_("No attendance records to create due to following reasons"),
		msg=message_table,
		as_table=True,
	)


def validate_employee(doc, confirmation: str) -> None:
	if confirmation != doc.employee:
		frappe.throw(_("Employee Code Confirmation does not match the selected employee."))

	if not frappe.db.exists("Employee", {"name": doc.employee, "company": doc.company, "status": "Active"}):
		frappe.throw(_("Employee {0} is not an active employee of {1}.").format(doc.employee, doc.company))


def get_request_days(doc, rows) -> list[dict]:
	if not rows:
		frappe.throw(_("Add at least one Request Date."))
	if len(rows) > MAX_DAYS:
		frappe.throw(_("Request at most {0} days at a time.").format(MAX_DAYS))

	from_date, to_date = getdate(doc.from_date), getdate(doc.to_date)
	days = {}
	for row in rows:
		request_date = getdate(row.get("request_date"))
		if not from_date <= request_date <= to_date:
			frappe.throw(_("Request Date {0} is not between From Date and To Date.").format(request_date))
		if request_date in days:
			frappe.throw(_("Request Date {0} is added more than once.").format(request_date))
		if row.get("reason") not in REASONS:
			frappe.throw(_("Select a Reason for Request Date {0}.").format(request_date))

		days[request_date] = {
			"request_date": request_date,
			"reason": row["reason"],
			"explanation": row.get("explanation") or "",
		}
	return [days[date] for date in sorted(days)]


def get_submitted_data() -> dict:
	data = frappe.form_dict.get("data")
	if isinstance(data, str):
		data = json.loads(data)
	return data or {}
