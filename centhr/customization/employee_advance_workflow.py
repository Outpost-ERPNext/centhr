"""Employee Advances (IOUs) are approved by the employee's line manager (HOD), then Finance 1, then Finance 2.

The IOU Dashboard (centhr.api.iou) shows these three steps as the approvers of each advance.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from centhr.customization.workflow import create_workflow

DOCTYPE = "Employee Advance"
WORKFLOW = "Employee Advance Approval"

STATE_OPEN = "Open"
STATE_HOD = "Approved by HOD"
STATE_FINANCE_1 = "Approved by Finance 1"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"

FINANCE_1_ROLE = "Accounts User"
FINANCE_2_ROLE = "Accounts Manager"

CUSTOM_FIELDS = {
	DOCTYPE: [
		{
			"fieldname": "line_manager",
			"fieldtype": "Link",
			"label": "Line Manager",
			"options": "User",
			"read_only": 1,
			"description": "The user of the employee's Reports To manager, who approves this advance first.",
			"insert_after": "department",
		}
	]
}

# The finance approvers have no access to Employee Advance in HRMS
PERMISSIONS = {
	FINANCE_1_ROLE: ("read", "write"),
	FINANCE_2_ROLE: ("read", "write", "submit"),
}


def setup_employee_advance_approval():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	add_finance_permissions()
	create_approval_workflow()


def add_finance_permissions():
	for role, ptypes in PERMISSIONS.items():
		if frappe.db.exists("Custom DocPerm", {"parent": DOCTYPE, "role": role, "permlevel": 0}):
			continue
		add_permission(DOCTYPE, role, 0)
		for ptype in ptypes:
			update_permission_property(DOCTYPE, role, 0, ptype, 1, validate=False)


def create_approval_workflow():
	"""Each step is taken by the approver stored on the advance (centhr.iou.routing) or their proxy.
	Finance 2's approval is the payment (centhr.iou.advance.pay_advance), so it has no Reject."""
	from centhr.iou.setup import steps

	create_workflow(
		WORKFLOW,
		DOCTYPE,
		states=[
			{"state": STATE_OPEN, "doc_status": 0, "allow_edit": "Employee"},
			{"state": STATE_HOD, "doc_status": 0, "allow_edit": FINANCE_1_ROLE},
			{"state": STATE_FINANCE_1, "doc_status": 0, "allow_edit": FINANCE_2_ROLE},
			{"state": STATE_APPROVED, "doc_status": 1, "allow_edit": FINANCE_2_ROLE},
			# Not submitted, so nothing is paid
			{"state": STATE_REJECTED, "doc_status": 0, "allow_edit": "HR Manager"},
		],
		transitions=[
			*steps(STATE_OPEN, STATE_HOD),
			*steps(STATE_HOD, STATE_FINANCE_1),
			*steps(STATE_FINANCE_1, STATE_APPROVED, can_reject=False),
		],
	)


def rebuild_approval_workflow():
	"""Patch: sites created before the approvers moved to CentHr Settings still have role-based steps."""
	if frappe.db.exists("Workflow", WORKFLOW):
		frappe.delete_doc("Workflow", WORKFLOW, ignore_permissions=True, force=True)
	create_approval_workflow()
