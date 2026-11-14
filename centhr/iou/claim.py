"""IOU claims and expense claims (Expense Claim): settle the open IOU first, the rest is paid to the employee.

- Claim = IOU outstanding: the whole claim is set off against the IOU, which is then closed.
- Claim < IOU outstanding: the IOU's outstanding goes down by the claim.
- Claim > IOU outstanding: the IOU covers its outstanding and the rest is payable to the employee
  (one claim: Expense Dr / Staff IOU Cr / Payable Cr, then Finance 1 pays the payable part).
- From pocket: no IOU; the whole claim is payable to the employee.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from centhr.iou import CLAIM, routing
from centhr.iou.advance import get_open_advance


def validate(doc):
	if frappe.flags.centhr_migration or doc.docstatus != 0:
		return

	if not doc.cost_center:
		doc.cost_center = frappe.get_cached_value("Company", doc.company, "cost_center")
	for row in doc.expenses:
		# Approvers change the claimed amount; the sanctioned amount follows it
		row.sanctioned_amount = row.amount
		# The web form does not ask for one; HRMS needs it to book the claim
		row.cost_center = row.cost_center or doc.cost_center
		if frappe.flags.in_web_form and doc.is_new() and not row.attachment:
			frappe.throw(_("Row {0}: attach the invoice or receipt stamped by Finance.").format(row.idx), title=_("Attachment Required"))
	if not doc.exchange_rate:
		doc.exchange_rate = 1
	if not doc.payable_account:
		doc.payable_account = frappe.get_cached_value("Company", doc.company, "default_expense_claim_payable_account")
	doc.expense_approver = doc.get("line_manager") or doc.expense_approver

	if doc.claim_from_pocket:
		doc.advances = []
	else:
		allocate_open_advance(doc)

	if doc.workflow_state == routing.STATE_REJECTED:
		doc.approval_status = "Rejected"


def allocate_open_advance(doc):
	total = sum(flt(row.amount) for row in doc.expenses) + flt(doc.get("total_taxes_and_charges"))
	advance = get_open_advance(doc.employee)
	if not advance:
		if doc.is_new() and not doc.advances:
			frappe.throw(
				_("You have no open IOU to settle. Tick 'Claim Expense from Pocket' to claim expenses you paid yourself."),
				title=_("No Open IOU"),
			)
		return

	if doc.is_new() and advance.due_date and getdate(today()) > getdate(advance.due_date):
		frappe.throw(
			_("IOU {0} was due on {1}. Claims can no longer be filed against it, and the outstanding amount will be deducted from your salary.").format(
				advance.name, frappe.format(advance.due_date, "Date")
			),
			title=_("IOU Past Due Date"),
		)

	if doc.is_new():
		validate_no_claim_in_approval(doc, advance.name)

	if not any(row.employee_advance == advance.name for row in doc.advances):
		from hrms.hr.doctype.expense_claim.expense_claim import get_expense_claim_advances

		doc.advances = []
		get_expense_claim_advances(doc, advance)

	# Settle the IOU first, up to the claim total
	remaining = flt(total)
	for row in doc.advances:
		available = flt(row.unclaimed_amount) - flt(row.return_amount)
		row.allocated_amount = max(min(available, remaining), 0)
		remaining -= row.allocated_amount


def validate_no_claim_in_approval(doc, advance: str):
	"""Each claim settles the IOU's outstanding as it is when filed, so claims against it go one at a time."""
	pending = claims_in_approval([advance])
	if pending:
		frappe.throw(
			_("Your IOU claim {0} against IOU {1} is still pending approval. File the next claim once it is approved or rejected.").format(
				pending[advance], advance
			),
			title=_("IOU Claim Pending Approval"),
		)


def claims_in_approval(advances: list[str]) -> dict[str, str]:
	"""{advance: claim} for claims against these IOUs that are neither approved nor rejected."""
	if not advances:
		return {}
	ec = frappe.qb.DocType(CLAIM)
	eca = frappe.qb.DocType("Expense Claim Advance")
	rows = (
		frappe.qb.from_(ec)
		.join(eca)
		.on(eca.parent == ec.name)
		.select(eca.employee_advance, ec.name)
		.where(
			(eca.employee_advance.isin(advances))
			& (ec.docstatus == 0)
			& ((ec.workflow_state.isnull()) | (ec.workflow_state != routing.STATE_REJECTED))
		)
	).run()
	return dict(rows)


def before_submit(doc):
	"""Finance 1's approval is the last step: HRMS books the claim only once it is Approved."""
	if frappe.flags.centhr_migration:
		return
	if doc.get("workflow_state") == routing.STATE_APPROVED:
		doc.approval_status = "Approved"


def amount_from_pocket(doc) -> float:
	"""What the company pays the employee in cash: the claim minus the IOU set off against it."""
	return flt(doc.grand_total)


def pay_claim(name: str, bank_account: str, reference_no: str | None = None) -> str:
	"""Finance 1 pays the part of an approved claim that the IOU did not cover (SOP: blue entries)."""
	from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

	from centhr.iou import settings

	doc = frappe.get_doc(CLAIM, name)
	if doc.docstatus != 1 or doc.approval_status != "Approved":
		frappe.throw(_("Expense Claim {0} must be approved before it is paid.").format(name))
	if flt(doc.grand_total) - flt(doc.total_amount_reimbursed) <= 0:
		frappe.throw(_("Expense Claim {0} has nothing left to pay.").format(name))
	user = frappe.session.user
	finance_1 = settings.finance_1()
	if user not in (finance_1, settings.proxy_for(finance_1)) and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only Finance 1 or their proxy can pay this claim."), frappe.PermissionError)

	pe = get_payment_entry_for_employee(CLAIM, name, bank_account=bank_account)
	pe.reference_no = reference_no or name
	pe.reference_date = today()
	pe.remarks = _("Amount {0} {1} to {2} against Claim Types ({3}) dated {4}").format(
		doc.currency,
		frappe.format(pe.paid_amount, "Currency"),
		doc.employee,
		", ".join(sorted({row.expense_type for row in doc.expenses})),
		frappe.format(doc.posting_date, "Date"),
	)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	return pe.name
