"""Custom fields and approval workflows of IOU Management. Runs after install and after every migrate."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from centhr.customization.workflow import create_workflow
from centhr.iou import ADVANCE, CLAIM, routing

CLAIM_WORKFLOW = "Expense Claim Approval"


def approval_fields(insert_after: str, finance_2: bool) -> list[dict]:
	"""Who has to act now, who acted, and when the step started (for the proxy escalation)."""
	fields = [
		{"fieldname": "iou_approval_section", "fieldtype": "Section Break", "label": "IOU Approval", "collapsible": 1, "insert_after": insert_after},
		{"fieldname": "current_approver", "fieldtype": "Link", "label": "Waiting For", "options": "User", "read_only": 1, "allow_on_submit": 1, "insert_after": "iou_approval_section"},
		{"fieldname": "proxy_approver", "fieldtype": "Link", "label": "Proxy", "options": "User", "read_only": 1, "allow_on_submit": 1, "insert_after": "current_approver"},
		{"fieldname": "pending_since", "fieldtype": "Datetime", "label": "Pending Since", "read_only": 1, "allow_on_submit": 1, "insert_after": "proxy_approver"},
		{"fieldname": "escalated_at", "fieldtype": "Datetime", "label": "Proxy Notified At", "read_only": 1, "allow_on_submit": 1, "insert_after": "pending_since"},
		{"fieldname": "iou_approval_column", "fieldtype": "Column Break", "insert_after": "escalated_at"},
		{"fieldname": "hod_approved_by", "fieldtype": "Link", "label": "HOD Approved By", "options": "User", "read_only": 1, "allow_on_submit": 1, "insert_after": "iou_approval_column"},
		{"fieldname": "finance_1_approved_by", "fieldtype": "Link", "label": "Finance 1 Approved By", "options": "User", "read_only": 1, "allow_on_submit": 1, "insert_after": "hod_approved_by"},
	]
	last = "finance_1_approved_by"
	if finance_2:
		fields.append({"fieldname": "finance_2_approved_by", "fieldtype": "Link", "label": "Finance 2 Approved By", "options": "User", "read_only": 1, "allow_on_submit": 1, "insert_after": last})
		last = "finance_2_approved_by"
	fields += [
		{"fieldname": "rejected_by", "fieldtype": "Link", "label": "Rejected By", "options": "User", "read_only": 1, "insert_after": last},
		{"fieldname": "rejected_stage", "fieldtype": "Data", "label": "Rejected At Stage", "read_only": 1, "insert_after": "rejected_by"},
		{"fieldname": "rejection_reason", "fieldtype": "Small Text", "label": "Reason for Rejection", "read_only": 1, "insert_after": "rejected_stage"},
	]
	return fields


CUSTOM_FIELDS = {
	ADVANCE: [
		{"fieldname": "purpose_type", "fieldtype": "Select", "label": "Purpose Type", "options": "\nTravel\nOther", "insert_after": "advance_amount"},
		{"fieldname": "iou_declaration", "fieldtype": "Check", "label": "I hereby declare that I am applying for an IOU. Any amount outstanding after the due date on this IOU will be deducted from my payroll.", "insert_after": "bank_ac_no"},
		{"fieldname": "payment_advice", "fieldtype": "Attach", "label": "Payment Advice", "read_only": 1, "allow_on_submit": 1, "insert_after": "iou_declaration"},
		*approval_fields("payment_advice", finance_2=True),
	],
	CLAIM: [
		{"fieldname": "claim_from_pocket", "fieldtype": "Check", "label": "Claim Expense from Pocket", "description": "Tick when you paid the expenses yourself and have no IOU to settle.", "insert_after": "employee_name"},
		{"fieldname": "line_manager", "fieldtype": "Link", "label": "Line Manager", "options": "User", "read_only": 1, "insert_after": "department"},
		*approval_fields("total_amount_reimbursed", finance_2=False),
	],
	"Expense Claim Detail": [
		{"fieldname": "attachment", "fieldtype": "Attach", "label": "Invoice / Receipt", "description": "Scanned invoice or receipt, stamped by Finance.", "insert_after": "amount"},
	],
}


def setup_iou():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	create_claim_workflow()


def approver_condition() -> str:
	return "frappe.session.user in (doc.current_approver, doc.proxy_approver)"


NO_APPROVER = "not doc.current_approver"


def steps(state: str, next_state: str, can_reject: bool = True) -> list[dict]:
	"""The approver (or proxy) of the state approves or rejects. HR steps in when there is no approver."""
	actions = [("Approve", next_state)] + ([("Reject", routing.STATE_REJECTED)] if can_reject else [])
	return [
		{"state": state, "action": action, "next_state": target, "allowed": allowed, "condition": condition}
		for action, target in actions
		for allowed, condition in (("All", approver_condition()), ("HR Manager", NO_APPROVER))
	]


def create_claim_workflow():
	create_workflow(
		CLAIM_WORKFLOW,
		CLAIM,
		states=[
			{"state": routing.STATE_OPEN, "doc_status": 0, "allow_edit": "Employee"},
			{"state": routing.STATE_HOD, "doc_status": 0, "allow_edit": "Accounts User"},
			{"state": routing.STATE_APPROVED, "doc_status": 1, "allow_edit": "Accounts User"},
			{"state": routing.STATE_REJECTED, "doc_status": 0, "allow_edit": "HR Manager"},
		],
		transitions=[
			*steps(routing.STATE_OPEN, routing.STATE_HOD),
			*steps(routing.STATE_HOD, routing.STATE_APPROVED),
		],
	)
