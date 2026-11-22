"""Compliance tab: statutory obligations accrued in the cycle, what was remitted, and payment deadlines."""

import calendar
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today
from frappe.utils.xlsxutils import build_xlsx_response

from centhr.payroll_dashboard import payment_request
from centhr.payroll_dashboard.scope import Scope

DUE_SOON_DAYS = 7
OPEN_STATES = (payment_request.PENDING, payment_request.APPROVED)


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
		order_by="posting_date asc",
	)
	payable = sum(flt(e.credit) for e in entries)
	remitted = sum(flt(e.debit) for e in entries)
	balance = flt(payable - remitted, 2)
	deadline = next_deadline(obligation, scope.to_date)
	requests = payment_request.get_requests("Statutory", [obligation.name])
	return {
		**obligation,
		"payable": payable,
		"remitted": remitted,
		"balance": balance,
		"accruals": vouchers(entries, "credit"),
		"payments": vouchers(entries, "debit"),
		"deadline": deadline,
		"status": deadline_status(balance, deadline),
		"requests": requests,
		# One request at a time: a pending or approved one has to be paid or rejected first
		"open_request": next((r.name for r in requests if r.status in OPEN_STATES), None),
	}


def vouchers(entries: list, side: str) -> list[dict]:
	"""The vouchers that accrued (credit) or remitted (debit) the obligation, with what each booked."""
	amounts: dict[tuple, float] = {}
	for entry in entries:
		if flt(entry[side]):
			key = (entry.voucher_type, entry.voucher_no, entry.posting_date)
			amounts[key] = amounts.get(key, 0) + flt(entry[side])
	return [
		{"voucher_type": voucher_type, "voucher_no": voucher_no, "date": posting_date, "amount": amount}
		for (voucher_type, voucher_no, posting_date), amount in amounts.items()
	]


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
	"""Ask Accounts to remit the obligation: a Payment Request Form that waits for approval."""
	doc = frappe.get_doc("Statutory Obligation", obligation)
	doc.check_permission("read")
	account = payment_account or doc.payment_account
	if not account:
		frappe.throw(_("Choose the bank or cash account to pay {0} from.").format(doc.obligation_name))
	if flt(amount) <= 0:
		frappe.throw(_("Nothing is outstanding for {0}.").format(doc.obligation_name))
	return payment_request.request_for_obligation(doc, amount, account)


def make_payment_entry(request) -> str:
	"""The draft bank entry of an approved request; Accounts reviews and submits it."""
	obligation = frappe.get_doc("Statutory Obligation", request.statutory_obligation)
	entry = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Bank Entry",
			"company": obligation.company,
			"posting_date": today(),
			"user_remark": _("{0}, payment request {1}").format(request.purpose, request.name),
			"accounts": [
				{"account": obligation.liability_account, "debit_in_account_currency": flt(request.amount)},
				{"account": request.payment_account, "credit_in_account_currency": flt(request.amount)},
			],
		}
	)
	entry.insert()
	return entry.name


class ObligationBreakdown:
	"""Who an obligation's liability of the cycle comes from: the salary components that HRMS books to
	its liability account, per employee, from the cycle's submitted salary slips. What the ledger
	holds beyond that was booked without a salary slip."""

	def __init__(self, obligation: str, scope: Scope):
		self.obligation = frappe.get_doc("Statutory Obligation", obligation)
		self.obligation.check_permission("read")
		frappe.has_permission("GL Entry", "read", throw=True)
		self.scope = Scope(self.obligation.company, scope.from_date, scope.to_date)
		self.components = self.get_components()

	def get_components(self) -> list[str]:
		"""Components by their account, never by their name."""
		return frappe.get_all(
			"Salary Component Account",
			filters={
				"parenttype": "Salary Component",
				"company": self.obligation.company,
				"account": self.obligation.liability_account,
			},
			pluck="parent",
			distinct=True,
		)

	def run(self) -> dict:
		rows = self.get_rows()
		total = sum(row["amount"] for row in rows)
		payable = summarize(self.obligation.as_dict(), self.scope)["payable"]
		return {
			"obligation": self.obligation.name,
			"obligation_name": self.obligation.obligation_name,
			"components": self.components,
			"rows": rows,
			"total": total,
			"payable": payable,
			# Booked to the liability account without a salary slip, such as a manual journal
			"difference": flt(payable - total, 2),
		}

	def get_rows(self) -> list[dict]:
		slips = {slip.name: slip for slip in self.scope.get_slips() if slip.docstatus == 1}
		if not slips or not self.components:
			return []
		lines = frappe.get_all(
			"Salary Detail",
			filters={
				"parenttype": "Salary Slip",
				"parent": ["in", list(slips)],
				"salary_component": ["in", self.components],
			},
			fields=["parent", "salary_component", "amount"],
		)
		rows: dict[str, dict] = {}
		for line in lines:
			slip = slips[line.parent]
			row = rows.setdefault(
				slip.name,
				{
					"employee": slip.employee,
					"employee_name": slip.employee_name,
					"department": slip.department,
					"salary_slip": slip.name,
					"currency": slip.currency,
					"components": {},
					"amount": 0.0,
				},
			)
			row["components"][line.salary_component] = (
				row["components"].get(line.salary_component, 0) + flt(line.amount)
			)
			row["amount"] += flt(line.amount)
		return sorted(rows.values(), key=lambda row: row["employee"])

	def export(self) -> None:
		result = self.run()
		header = ["Employee ID", "Employee Name", "Department", "Salary Slip", *self.components, "Total"]
		data = [
			[
				row["employee"],
				row["employee_name"],
				row["department"],
				row["salary_slip"],
				*[row["components"].get(component, 0) for component in self.components],
				row["amount"],
			]
			for row in result["rows"]
		]
		build_xlsx_response(
			[header, *data],
			f"{self.obligation.obligation_name} {self.scope.from_date} to {self.scope.to_date}",
		)
