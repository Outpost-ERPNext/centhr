"""Approve, Reject and Modify on the IOU Dashboard (SOP: approval, rejection and modification steps)."""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import flt

from centhr.iou import ADVANCE, CLAIM, IOU_DOCTYPES, notifications, routing

APPROVE = "Approve"
REJECT = "Reject"
MODIFY = "Modify"
PAY = "Pay"


def get_document(doctype: str, name: str):
	if doctype not in IOU_DOCTYPES:
		frappe.throw(_("Not an IOU document: {0}").format(doctype))
	return frappe.get_doc(doctype, name)


def available_actions(doc, user: str | None = None) -> list[str]:
	"""What the user can do with the document now."""
	user = user or frappe.session.user
	if doc.docstatus == 1:
		if doc.doctype == CLAIM and can_pay_claim(doc, user):
			return [PAY]
		return []
	if not routing.can_act(doc, user):
		return []
	stage = routing.stage_of(doc)
	if stage == routing.FINANCE_2:
		# SOP: Finance 2 neither rejects nor modifies; it pays (and must not be the Finance 1 approver)
		return [] if doc.get("finance_1_approved_by") == user else [PAY]
	return [APPROVE, REJECT, MODIFY]


def can_pay_claim(doc, user: str) -> bool:
	from centhr.iou import settings

	if flt(doc.grand_total) - flt(doc.total_amount_reimbursed) <= 0:
		return False
	finance_1 = settings.finance_1()
	return user in (finance_1, settings.proxy_for(finance_1))


def approve(doctype: str, name: str):
	doc = get_document(doctype, name)
	require(doc, APPROVE)
	apply_workflow(doc, APPROVE)


def reject(doctype: str, name: str, reason: str):
	doc = get_document(doctype, name)
	require(doc, REJECT)
	if not (reason or "").strip():
		frappe.throw(_("Enter the reason for rejection."), title=_("Reason Required"))
	doc.db_set("rejection_reason", reason.strip())
	apply_workflow(doc, REJECT)


def modify(doctype: str, name: str, advance_amount: float | None = None, expenses: str | list | None = None):
	"""The approver changes the IOU amount, or the claim type and amount of claim rows."""
	doc = get_document(doctype, name)
	require(doc, MODIFY)
	acted_as = routing.acted_as(doc, frappe.session.user, routing.stage_of(doc))

	changes = []
	if doctype == ADVANCE:
		amount = flt(advance_amount)
		if amount <= 0:
			frappe.throw(_("Enter the modified advance amount."))
		if amount != flt(doc.advance_amount):
			changes.append(_("Advance Amount: {0} → {1}").format(doc.advance_amount, amount))
			doc.advance_amount = amount
	else:
		changes = modify_expenses(doc, frappe.parse_json(expenses) if isinstance(expenses, str) else expenses or [])

	if not changes:
		frappe.throw(_("Nothing was changed."))

	doc.flags.ignore_permissions = True
	doc.save()
	doc.add_comment("Edit", _("Modified by {0} – {1}: {2}").format(acted_as, frappe.session.user, "; ".join(changes)))
	notifications.notify_modified(doc, acted_as)


def modify_expenses(doc, rows: list[dict]) -> list[str]:
	by_name = {row.name: row for row in doc.expenses}
	changes = []
	for change in rows:
		row = by_name.get(change.get("name"))
		if not row:
			frappe.throw(_("Row {0} is not in this claim.").format(change.get("name")))
		expense_type = change.get("expense_type") or row.expense_type
		amount = flt(change.get("amount", row.amount))
		if amount <= 0:
			frappe.throw(_("Row {0}: the amount must be more than zero.").format(row.idx))
		if expense_type != row.expense_type:
			changes.append(_("Row {0} Claim Type: {1} → {2}").format(row.idx, row.expense_type, expense_type))
			row.expense_type = expense_type
			row.default_account = None
		if amount != flt(row.amount):
			changes.append(_("Row {0} Amount: {1} → {2}").format(row.idx, row.amount, amount))
			row.amount = amount
	return changes


def require(doc, action: str):
	if action not in available_actions(doc):
		frappe.throw(_("You cannot {0} {1} {2} now.").format(_(action).lower(), _(doc.doctype), doc.name), frappe.PermissionError)
