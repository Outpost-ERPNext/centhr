"""Applies the leave policy to the site on migrate: fields, Leave Type settings, cadre days and the approval workflow."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from centhr.customization.workflow import create_workflow
from centhr.leave_policy.rules import ADOPTION, PATERNITY, RULES

# Annual Leave days per cadre, filled in on grades that have none yet; HR can change them on the grade
CADRE_DAYS = {"Junior Level": 15, "Medium Level": 20, "Senior Level": 25, "Expat": 30}
# Carried forward leave lasts about a quarter; the exact end of March is set per allocation
CARRY_FORWARD_EXPIRY_DAYS = 90

WORKFLOW = "Leave Approval"
HOD_APPROVED = "Approved by HOD"

CUSTOM_FIELDS = {
	"Employee Grade": [
		{
			"fieldname": "annual_leave_days",
			"fieldtype": "Float",
			"label": "Annual Leave Days",
			"description": "Annual Leave a confirmed employee of this cadre earns in a calendar year.",
			"insert_after": "default_base_pay",
		}
	],
	"Leave Application": [
		{
			"fieldname": "child_date_of_birth",
			"fieldtype": "Date",
			"label": "Child's Date of Birth",
			"depends_on": f"eval:['{PATERNITY}', '{ADOPTION}'].includes(doc.leave_type)",
			"insert_after": "leave_type",
		}
	],
}


def setup_leave_policy():
	create_custom_fields(CUSTOM_FIELDS, update=True)
	configure_leave_types()
	set_cadre_days()
	create_leave_workflow()


def configure_leave_types():
	for leave_type, rule in RULES.items():
		if not frappe.db.exists("Leave Type", leave_type):
			continue
		doc = frappe.get_doc("Leave Type", leave_type)
		doc.update(
			{
				"include_holiday": int(rule.include_holidays),
				"is_carry_forward": int(bool(rule.carry_forward_days)),
				"maximum_carry_forwarded_leaves": rule.carry_forward_days,
				"expire_carry_forwarded_leaves_after_days": CARRY_FORWARD_EXPIRY_DAYS if rule.carry_forward_days else 0,
				# Annual Leave starts the year at zero and grows monthly, which HRMS allows for earned leave only.
				# HRMS's own earned leave job skips it: that job only handles allocations from a leave policy.
				"is_earned_leave": int(rule.yearly_days is None),
				"earned_leave_frequency": "Monthly",
				"max_leaves_allowed": rule.yearly_days or 0,
				"allow_negative": 0,
				"is_lwp": 0,
			}
		)
		doc.save(ignore_permissions=True)


def set_cadre_days():
	for grade, days in CADRE_DAYS.items():
		if not frappe.db.exists("Employee Grade", grade):
			frappe.get_doc({"doctype": "Employee Grade", "__newname": grade}).insert(ignore_permissions=True)
		if not frappe.db.get_value("Employee Grade", grade, "annual_leave_days"):
			frappe.db.set_value("Employee Grade", grade, "annual_leave_days", days)


def create_leave_workflow():
	"""HOD (the leave approver) approves first, then HR. Either can reject."""
	is_hod = "doc.leave_approver == frappe.session.user"
	create_workflow(
		WORKFLOW,
		"Leave Application",
		states=[
			{"state": "Open", "doc_status": 0, "update_field": "status", "update_value": "Open", "allow_edit": "Employee"},
			{"state": HOD_APPROVED, "doc_status": 0, "update_field": "status", "update_value": "Open", "allow_edit": "HR Manager"},
			{"state": "Approved", "doc_status": 1, "update_field": "status", "update_value": "Approved", "allow_edit": "HR Manager"},
			{"state": "Rejected", "doc_status": 1, "update_field": "status", "update_value": "Rejected", "allow_edit": "HR Manager"},
		],
		transitions=[
			{"state": "Open", "action": "Approve", "next_state": HOD_APPROVED, "allowed": "Leave Approver", "condition": is_hod},
			{"state": "Open", "action": "Reject", "next_state": "Rejected", "allowed": "Leave Approver", "condition": is_hod},
			{"state": HOD_APPROVED, "action": "Approve", "next_state": "Approved", "allowed": "HR Manager"},
			{"state": HOD_APPROVED, "action": "Reject", "next_state": "Rejected", "allowed": "HR Manager"},
		],
	)
