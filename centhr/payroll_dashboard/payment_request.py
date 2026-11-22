"""Payment requests: what a payroll run or a statutory obligation asks Accounts to pay, and its approval."""

import frappe
from frappe import _
from frappe.utils import flt

from centhr.centhr.doctype.payment_request_form.payment_request_form import (
	APPROVED,
	APPROVER_ROLES,
	PENDING,
	REJECTED,
	SUBJECT_FIELD,
)

DOCTYPE = "Payment Request Form"
FIELDS = [
	"name",
	"status",
	"amount",
	"currency",
	"payment_account",
	"journal_entry",
	"requested_by",
	"approved_by",
	"approved_on",
	"rejection_reason",
	"creation",
]


def request_for_run(entry, payment_account: str | None = None) -> str:
	"""Ask Accounts to pay a payroll entry whose salary slips are submitted."""
	entry.check_permission("write")
	return (
		frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"request_type": "Payroll",
				"company": entry.company,
				"payroll_entry": entry.name,
				"amount": get_payable_amount(entry),
				"payment_account": payment_account or entry.payment_account,
				"purpose": _("Salaries of {0} to {1}, payroll entry {2}").format(
					frappe.format(entry.start_date, "Date"), frappe.format(entry.end_date, "Date"), entry.name
				),
			}
		)
		.insert()
		.name
	)


def request_for_obligation(obligation, amount: float, payment_account: str) -> str:
	return (
		frappe.get_doc(
			{
				"doctype": DOCTYPE,
				"request_type": "Statutory",
				"company": obligation.company,
				"statutory_obligation": obligation.name,
				"amount": flt(amount),
				"payment_account": payment_account,
				"purpose": _("Remittance of {0}").format(obligation.obligation_name),
			}
		)
		.insert()
		.name
	)


def get_payable_amount(entry) -> float:
	"""What the run's accrual journals credited to payroll payable; the net pay of its submitted
	slips when it has no accrual yet. Withheld salaries are paid later, by their own bank entry."""
	slips = frappe.get_all(
		"Salary Slip",
		filters={"payroll_entry": entry.name, "docstatus": 1},
		fields=["name", "net_pay", "journal_entry", "status"],
	)
	net_pay = sum(flt(slip.net_pay) for slip in slips if slip.status != "Withheld")
	withheld = sum(flt(slip.net_pay) for slip in slips if slip.status == "Withheld")
	journals = list({slip.journal_entry for slip in slips if slip.journal_entry})
	if not journals or any(not slip.journal_entry for slip in slips):
		return net_pay
	lines = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": ["in", journals], "account": entry.payroll_payable_account, "docstatus": 1},
		fields=["credit_in_account_currency", "debit_in_account_currency"],
	)
	booked = sum(flt(line.credit_in_account_currency) - flt(line.debit_in_account_currency) for line in lines)
	return flt(booked - withheld, 2) or net_pay


def get_latest(request_type: str, subject: str) -> dict | None:
	"""The newest request of a payroll entry or an obligation, whatever its state."""
	rows = get_requests(request_type, [subject], limit=1)
	return rows[0] if rows else None


def get_requests(request_type: str, subjects: list[str], limit: int = 0) -> list[dict]:
	if not subjects:
		return []
	subject = SUBJECT_FIELD[request_type]
	rows = frappe.get_all(
		DOCTYPE,
		filters={subject: ["in", subjects]},
		fields=[*FIELDS, subject],
		order_by="creation desc",
		limit=limit,
	)
	can_decide = can_approve()
	names = {user: full_name(user) for row in rows for user in (row.requested_by, row.approved_by) if user}
	for row in rows:
		row.requested_by_name = names.get(row.requested_by)
		row.approved_by_name = names.get(row.approved_by)
		row.can_decide = can_decide and row.status == PENDING
	return rows


def is_open(request: dict | None) -> bool:
	return bool(request) and request["status"] != REJECTED


def can_approve() -> bool:
	return bool(set(APPROVER_ROLES).intersection(frappe.get_roles()))


def decide(name: str, approve: bool, reason: str | None = None) -> dict:
	"""Approve or reject a request. An approved statutory request gets its draft bank entry at once;
	a payroll run's is made by the run's own bank entry step."""
	request = frappe.get_doc(DOCTYPE, name)
	if not approve:
		request.reject(reason)
	else:
		request.approve()
		if request.request_type == "Statutory":
			from centhr.payroll_dashboard.compliance import make_payment_entry

			request.set_bank_entry(make_payment_entry(request))
	return {"name": request.name, "status": request.status}


def link_bank_entry(payroll_entry: str, journal_entry: str) -> None:
	"""The run's bank entry pays its approved request."""
	name = frappe.db.get_value(DOCTYPE, {"payroll_entry": payroll_entry, "status": APPROVED})
	if name:
		frappe.get_doc(DOCTYPE, name).set_bank_entry(journal_entry)


def close_for_cancelled_run(payroll_entry: str) -> None:
	"""A cancelled payroll entry has nothing left to pay."""
	for name in frappe.get_all(
		DOCTYPE, filters={"payroll_entry": payroll_entry, "status": ["in", [PENDING, APPROVED]]}, pluck="name"
	):
		frappe.db.set_value(
			DOCTYPE, name, {"status": REJECTED, "rejection_reason": _("The payroll entry was cancelled.")}
		)


def full_name(user: str) -> str:
	return frappe.db.get_value("User", user, "full_name", cache=True) or user
