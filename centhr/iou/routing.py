"""Who has to act on an IOU document next, and who acted on it.

Each pending workflow state belongs to one stage. The stage's approver and their proxy are stored on the
document (`current_approver`, `proxy_approver`), so the workflow conditions, the dashboard and the
escalation job read them from one place.
"""

import frappe
from frappe.share import add_docshare
from frappe.utils import now_datetime

from centhr.iou import ADVANCE, settings
from centhr.overrides.attendance_request import get_line_manager

STATE_OPEN = "Open"
STATE_HOD = "Approved by HOD"
STATE_FINANCE_1 = "Approved by Finance 1"
STATE_APPROVED = "Approved"
STATE_REJECTED = "Rejected"

HOD = "HOD"
FINANCE_1 = "Finance 1"
FINANCE_2 = "Finance 2"

# Stage whose approval each state waits for
PENDING_STAGE = {
	ADVANCE: {STATE_OPEN: HOD, STATE_HOD: FINANCE_1, STATE_FINANCE_1: FINANCE_2},
	"Expense Claim": {STATE_OPEN: HOD, STATE_HOD: FINANCE_1},
}

# Field that records who gave each stage's approval
APPROVED_BY_FIELD = {HOD: "hod_approved_by", FINANCE_1: "finance_1_approved_by", FINANCE_2: "finance_2_approved_by"}


def state_of(doc) -> str:
	return doc.get("workflow_state") or STATE_OPEN


def stage_of(doc, state: str | None = None) -> str | None:
	return PENDING_STAGE[doc.doctype].get(state or state_of(doc))


def approver_for(doc, stage: str | None) -> str | None:
	if stage == HOD:
		return doc.get("line_manager")
	if stage == FINANCE_1:
		return settings.finance_1()
	if stage == FINANCE_2:
		return settings.finance_2()
	return None


def route(doc):
	"""validate: set the line manager, the approver of the current stage and their proxy.
	Records who approved the previous stage when the state moves on."""
	if doc.docstatus == 0 and not frappe.flags.centhr_migration:
		doc.line_manager = get_line_manager(doc.employee)

	previous = doc.get_doc_before_save()
	previous_state = state_of(previous) if previous else None
	state = state_of(doc)

	if previous and previous_state != state:
		record_actor(doc, previous, previous_state, state)

	# A submitted document waits for nobody
	stage = stage_of(doc, state) if doc.docstatus == 0 else None
	approver = approver_for(doc, stage) if stage else None
	doc.current_approver = approver
	doc.proxy_approver = settings.proxy_for(approver)

	if not previous or previous_state != state:
		doc.pending_since = now_datetime() if stage else None
		doc.escalated_at = None


def record_actor(doc, previous, previous_state: str, state: str):
	user = frappe.session.user
	stage = stage_of(doc, previous_state)
	if state == STATE_REJECTED:
		doc.rejected_by = user
		doc.rejected_stage = stage
	elif stage:
		doc.set(APPROVED_BY_FIELD[stage], user)
	doc.flags.iou_acted_as = acted_as(previous, user, stage)


def acted_as(previous, user: str, stage: str | None) -> str:
	"""'HOD', 'Finance 1'… or "HOD's proxy" when the proxy acted for the approver."""
	if not stage:
		return ""
	if previous.get("proxy_approver") == user and previous.get("current_approver") != user:
		return f"{stage}'s proxy"
	return stage


def can_act(doc, user: str | None = None) -> bool:
	"""The approver of the current stage or their proxy. HR acts when the employee has no line manager."""
	user = user or frappe.session.user
	if not stage_of(doc) or doc.docstatus != 0:
		return False
	if user in (doc.get("current_approver"), doc.get("proxy_approver")):
		return True
	return not doc.get("current_approver") and "HR Manager" in frappe.get_roles(user)


def share_with_approvers(doc):
	"""on_update: approvers often have only the Employee role. A share lets them open, change and
	submit this one document."""
	if frappe.flags.centhr_migration or doc.docstatus != 0:
		return
	for user in {doc.get("current_approver"), doc.get("proxy_approver")} - {None, "", frappe.session.user}:
		add_docshare(
			doc.doctype,
			doc.name,
			user,
			read=1,
			write=1,
			submit=1,
			notify=0,
			flags={"ignore_share_permission": True},
		)
