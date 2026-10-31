# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate

SAVEPOINT = "checkin_attendance"


def mark_attendance_from_checkin(doc, method=None):
	"""Marks the employee Present on the day of their first check-in.

	HRMS only turns check-ins into attendance through auto attendance on a Shift Type, a scheduled job.
	Check-ins whose shift uses it are left to HRMS. A failure is logged and never blocks the check-in."""
	if not needs_attendance(doc):
		return

	frappe.db.savepoint(SAVEPOINT)
	try:
		attendance = create_attendance(doc)
		# Linked the way HRMS auto attendance links its check-ins; db_set does not fire on_update
		doc.db_set("attendance", attendance.name, update_modified=False)
	except Exception:
		frappe.db.rollback(save_point=SAVEPOINT)
		frappe.log_error(
			title="Attendance from Employee Checkin failed",
			reference_doctype="Employee Checkin",
			reference_name=doc.name,
		)


def needs_attendance(doc) -> bool:
	if not doc.employee or not doc.time or doc.skip_auto_attendance or doc.attendance:
		return False
	if doc.shift and frappe.db.get_value("Shift Type", doc.shift, "enable_auto_attendance"):
		return False
	# Only the first check-in of the day; any later one finds this attendance
	return not frappe.db.exists(
		"Attendance",
		{"employee": doc.employee, "attendance_date": getdate(doc.time), "docstatus": ("<", 2)},
	)


def create_attendance(doc):
	attendance = frappe.new_doc("Attendance")
	attendance.update(
		{
			"employee": doc.employee,
			"company": frappe.db.get_value("Employee", doc.employee, "company"),
			"attendance_date": getdate(doc.time),
			"status": "Present",
			"shift": doc.shift,
			"in_time": doc.time if doc.log_type in (None, "", "IN") else None,
		}
	)
	# Employees check in through the guest web form too
	attendance.flags.ignore_permissions = True
	attendance.insert()
	attendance.submit()
	return attendance
