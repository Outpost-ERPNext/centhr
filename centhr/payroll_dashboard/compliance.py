"""Compliance tab: statutory obligations accrued in the cycle, what was remitted, and payment deadlines."""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today

from centhr.payroll_dashboard.scope import Scope

DUE_SOON_DAYS = 7
# Draft journal entries made by Request Payment carry this remark, so they show as open requests
REQUEST_REMARK = "Statutory Obligation: {0}"


def get_compliance(scope: Scope) -> dict:
	if not frappe.has_permission("GL Entry", "read"):
		return {"no_access": True, "obligations": []}
	obligations = frappe.get_list(
		"Statutory Obligation",
		filters={**scope.company_filter, "disabled": 0},
		fields=["name", "obligation_name", "company", "liability_account", "payment_account", "frequency", "due_day", "due_months"],
		order_by="obligation_name asc",
	)
	return {"obligations": [summarize(o, scope) for o in obligations]}


def summarize(obligation, scope: Scope) -> dict:
	entries = frappe.get_all(
		"GL Entry",
		filters={
			"account": obligation.liability_account,
			"is_cancelled": 0,
			"posting_date": ["between", [scope.from_date, scope.to_date]],
		},
		fields=["voucher_type", "voucher_no", "debit", "credit", "posting_date"],
	)
	payable = sum(flt(e.credit) for e in entries)
	remitted = sum(flt(e.debit) for e in entries)
	balance = flt(payable - remitted, 2)
	deadline = next_deadline(obligation, scope.to_date)
	return {
		**obligation,
		"payable": payable,
		"remitted": remitted,
		"balance": balance,
		"accruals": sorted({e.voucher_no for e in entries if flt(e.credit)}),
		"payments": [{"voucher_no": e.voucher_no, "amount": e.debit, "date": e.posting_date} for e in entries if flt(e.debit)],
		"deadline": deadline,
		"status": deadline_status(balance, deadline),
		"open_requests": frappe.get_all(
			"Journal Entry",
			filters={"docstatus": 0, "user_remark": REQUEST_REMARK.format(obligation.name)},
			pluck="name",
		),
	}


def next_deadline(obligation, cycle_end: date) -> date:
	"""Monthly obligations fall due the month after the cycle; others in their next due month after it."""
	doc = frappe.get_doc("Statutory Obligation", obligation.name)
	months = doc.due_month_list()
	if not months:
		return due_date(getdate(add_months(cycle_end, 1)), obligation.due_day)
	for offset in range(0, 13):
		month = getdate(add_months(cycle_end, offset))
		if month.month in months:
			candidate = due_date(month, obligation.due_day)
			if candidate >= cycle_end:
				return candidate
	return due_date(getdate(add_months(cycle_end, 12)), obligation.due_day)


def due_date(month: date, day: int) -> date:
	last = calendar.monthrange(month.year, month.month)[1]
	return date(month.year, month.month, min(max(day or 1, 1), last))


def deadline_status(balance: float, deadline: date) -> str:
	if balance <= 0:
		return "Settled"
	days_left = (deadline - getdate(today())).days
	if days_left < 0:
		return "Overdue"
	return "Due Soon" if days_left <= DUE_SOON_DAYS else "On Track"


def request_payment(obligation: str, amount: float, payment_account: str | None = None) -> str:
	"""A draft bank entry that pays the obligation; Accounts reviews and submits it."""
	doc = frappe.get_doc("Statutory Obligation", obligation)
	account = payment_account or doc.payment_account
	if not account:
		frappe.throw(_("Choose the bank or cash account to pay {0} from.").format(doc.obligation_name))
	if flt(amount) <= 0:
		frappe.throw(_("Nothing is outstanding for {0}.").format(doc.obligation_name))
	entry = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Bank Entry",
			"company": doc.company,
			"posting_date": today(),
			"user_remark": REQUEST_REMARK.format(doc.name),
			"accounts": [
				{"account": doc.liability_account, "debit_in_account_currency": flt(amount)},
				{"account": account, "credit_in_account_currency": flt(amount)},
			],
		}
	)
	entry.insert()
	return entry.name

