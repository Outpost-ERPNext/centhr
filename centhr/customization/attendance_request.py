"""Attendance Requests are approved by the employee's line manager alone.

Check-ins need no approval: centhr.api.employee_checkin_attendance marks the employee Present.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from centhr.customization.workflow import create_workflow

WORKFLOW = "Attendance Approval"

CUSTOM_FIELDS = {
	"Attendance Request": [
		{
			"fieldname": "line_manager",
			"fieldtype": "Link",
			"label": "Line Manager",
			"options": "User",
			"read_only": 1,
			"description": "The user of the employee's Reports To manager, who approves this request.",
			"insert_after": "department",
		}
	]
}


def setup_attendance_approval():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	create_approval_workflow()


def create_approval_workflow():
	# HR steps in only for employees whose line manager has no user to approve with
	is_line_manager = "doc.line_manager == frappe.session.user"
	no_line_manager = "not doc.line_manager"
	create_workflow(
		WORKFLOW,
		"Attendance Request",
		states=[
			{"state": "Open", "doc_status": 0, "allow_edit": "Employee"},
			{"state": "Approved", "doc_status": 1, "allow_edit": "HR Manager"},
			# Not submitted, so no attendance is marked
			{"state": "Rejected", "doc_status": 0, "allow_edit": "HR Manager"},
		],
		transitions=[
			{"state": "Open", "action": "Approve", "next_state": "Approved", "allowed": "Employee", "condition": is_line_manager},
			{"state": "Open", "action": "Reject", "next_state": "Rejected", "allowed": "Employee", "condition": is_line_manager},
			{"state": "Open", "action": "Approve", "next_state": "Approved", "allowed": "HR Manager", "condition": no_line_manager},
			{"state": "Open", "action": "Reject", "next_state": "Rejected", "allowed": "HR Manager", "condition": no_line_manager},
		],
	)
