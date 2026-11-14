"""IOU applications (Employee Advance): SOP rules, due date and payment."""

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, cint, flt, getdate, today

from centhr.iou import ADVANCE, notifications, routing, settings

TRAVEL = "Travel"
OTHER = "Other"


def outstanding(advance) -> float:
	"""Paid but not yet settled by a claim or a return (salary deductions count as returns)."""
	return flt(advance.paid_amount) - flt(advance.claimed_amount) - flt(advance.return_amount)


def due_date(purpose_type: str, tenure, payment_date):
	"""SOP: Travel = payment date + tenure + 7 days. Other = payment date + 5 days."""
	if purpose_type == TRAVEL:
		return add_days(payment_date, cint(tenure) + settings.get_int("iou_travel_grace_days"))
	return add_days(payment_date, settings.get_int("iou_other_due_days"))


# ---------------------------------------------------------------- validation


def validate(doc):
	if frappe.flags.centhr_migration:
		return
	if doc.docstatus == 0:
		validate_application(doc)
		doc.repay_unclaimed_amount_from_salary = 1
		if not doc.currency:
			doc.currency = frappe.get_cached_value("Company", doc.company, "default_currency")
	if doc.is_new():
		validate_no_open_iou(doc)


def validate_application(doc):
	if not doc.purpose_type:
		frappe.throw(_("Select the Purpose Type of the IOU."), title=_("Purpose Type Required"))
	if doc.purpose_type == TRAVEL:
		tenure = str(doc.tenure or "").strip()
		if not tenure.isdigit() or int(tenure) <= 0:
			frappe.throw(_("Enter the travel tenure as a number of days."), title=_("Tenure Required"))
		doc.tenure = str(int(tenure))
	else:
		doc.tenure = None
	if doc.is_new() and not doc.iou_declaration:
		frappe.throw(_("Tick the declaration to apply for the IOU."), title=_("Declaration Required"))


def validate_no_open_iou(doc):
	"""SOP: an employee cannot apply for a new IOU while another is in approval or not settled."""
	advances = frappe.get_all(
		ADVANCE,
		filters={"employee": doc.employee, "docstatus": ["<", 2], "name": ["!=", doc.name or ""]},
		fields=["name", "docstatus", "workflow_state", "paid_amount", "claimed_amount", "return_amount", "currency"],
	)
	for advance in advances:
		if advance.docstatus == 0 and advance.workflow_state != routing.STATE_REJECTED:
			frappe.throw(
				_(
					"Your IOU application {0} is still pending approval. You can apply for a new IOU once it is approved or rejected."
				).format(advance.name),
				title=_("IOU Pending Approval"),
			)
		if advance.docstatus == 1 and outstanding(advance) > 0:
			frappe.throw(
				_(
					"You have not settled IOU {0}. Outstanding amount: {1} {2}. Settle it with an IOU claim before you apply for a new IOU."
				).format(advance.name, advance.currency, frappe.format(outstanding(advance), "Currency")),
				title=_("Outstanding IOU"),
			)


def before_submit(doc):
	"""The last approval is Finance 2's payment, which only pay_advance makes."""
	if frappe.flags.centhr_migration or frappe.flags.iou_paying:
		return
	if frappe.get_meta(ADVANCE).has_field("workflow_state") and doc.get("workflow_state") == routing.STATE_APPROVED:
		frappe.throw(_("Use Pay on the IOU Dashboard to approve and pay this IOU."), title=_("Payment Required"))


# ---------------------------------------------------------------- payment


def pay_advance(name: str, bank_account: str, reference_no: str | None = None, payment_advice: str | None = None) -> str:
	"""Finance 2 approves the IOU and pays it (SOP: Steps for IOU Approver, Finance 2).

	Posts Staff IOU Dr / Bank Cr through a Payment Entry, then starts the settlement period."""
	from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

	doc = frappe.get_doc(ADVANCE, name)
	if routing.state_of(doc) != routing.STATE_FINANCE_1 or doc.docstatus != 0:
		frappe.throw(_("IOU {0} is not waiting for payment.").format(name))
	if not routing.can_act(doc):
		frappe.throw(_("Only Finance 2 or their proxy can pay this IOU."), frappe.PermissionError)
	if doc.finance_1_approved_by == frappe.session.user:
		frappe.throw(_("You approved this IOU as Finance 1, so another Finance user must pay it."), frappe.PermissionError)

	frappe.flags.iou_paying = True
	try:
		apply_workflow(doc, "Approve")
	finally:
		frappe.flags.iou_paying = False
	doc.reload()

	pe = get_payment_entry_for_employee(ADVANCE, name, bank_account=bank_account)
	pe.reference_no = reference_no or name
	pe.reference_date = today()
	pe.remarks = _("IOU {0} paid to {1} ({2}) for: {3}").format(name, doc.employee_name, doc.employee, doc.purpose)
	pe.flags.ignore_permissions = True
	pe.insert()
	pe.submit()
	if payment_advice:
		attach(payment_advice, "Payment Entry", pe.name)
		doc.db_set("payment_advice", payment_advice)

	payment_date = getdate(pe.posting_date)
	doc.db_set({"payment_date": payment_date, "due_date": due_date(doc.purpose_type, doc.tenure, payment_date)})
	doc.reload()
	notifications.notify_paid(doc)
	return pe.name


def attach(file_url: str, doctype: str, name: str):
	"""Attaches the payment advice that the dashboard uploaded (unattached) to the Payment Entry."""
	uploaded = frappe.db.get_value(
		"File", {"file_url": file_url, "attached_to_name": ["is", "not set"], "owner": frappe.session.user}, "name"
	)
	if uploaded:
		frappe.db.set_value("File", uploaded, {"attached_to_doctype": doctype, "attached_to_name": name})
		return
	frappe.get_doc(
		{"doctype": "File", "file_url": file_url, "attached_to_doctype": doctype, "attached_to_name": name}
	).insert(ignore_permissions=True)


def get_open_advance(employee: str):
	"""The paid IOU the employee still has to settle, if any (at most one, SOP)."""
	for advance in frappe.get_all(
		ADVANCE,
		filters={"employee": employee, "docstatus": 1, "paid_amount": [">", 0]},
		fields=["name", "posting_date", "purpose", "paid_amount", "claimed_amount", "return_amount", "advance_account", "due_date", "currency"],
		order_by="posting_date asc",
	):
		if outstanding(advance) > 0:
			advance.outstanding_amount = outstanding(advance)
			return advance
	return None
