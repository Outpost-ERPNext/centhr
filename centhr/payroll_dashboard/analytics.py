"""Analytics tab: the cycle's payroll by department, component and employee, over months, and against the books."""

from collections import defaultdict

import frappe
from frappe.utils import flt

from centhr.payroll_dashboard.scope import Scope, totals

MONTHS_COMPARED = 6


def get_analytics(scope: Scope, view: str) -> dict:
	views = {
		"department": by_department,
		"component": by_component,
		"employee": by_employee,
		"months": by_month,
		"journal": journal_summary,
	}
	if view not in views:
		frappe.throw(frappe._("Unknown analytics view {0}.").format(view))
	return views[view](scope)


def by_department(scope: Scope) -> dict:
	groups = defaultdict(list)
	for slip in scope.get_slips():
		groups[slip.department or frappe._("No department")].append(slip)
	rows = [{"department": name, **totals(slips)} for name, slips in groups.items()]
	return {"rows": sorted(rows, key=lambda r: -r["net_pay"])}


def by_component(scope: Scope) -> dict:
	slips = scope.get_slips(["name"])
	if not slips:
		return {"rows": []}
	details = frappe.get_all(
		"Salary Detail",
		filters={"parenttype": "Salary Slip", "parent": ["in", [s.name for s in slips]]},
		fields=["salary_component", "parentfield", "amount", "parent"],
	)
	groups = defaultdict(lambda: {"amount": 0.0, "slips": set()})
	for d in details:
		group = groups[(d.salary_component, d.parentfield)]
		group["amount"] += flt(d.amount)
		group["slips"].add(d.parent)
	rows = [
		{
			"salary_component": component,
			"type": "Earning" if field == "earnings" else "Deduction",
			"amount": g["amount"],
			"employees": len(g["slips"]),
		}
		for (component, field), g in groups.items()
	]
	return {"rows": sorted(rows, key=lambda r: (r["type"], -r["amount"]))}


def by_employee(scope: Scope) -> dict:
	slips = scope.get_slips()
	total_net = sum(s.net_pay or 0 for s in slips) or 1
	rows = [{**s, "share": flt(s.net_pay) / total_net * 100} for s in slips]
	return {"rows": sorted(rows, key=lambda r: -flt(r["net_pay"]))}


def by_month(scope: Scope) -> dict:
	rows = []
	for back in range(MONTHS_COMPARED - 1, -1, -1):
		cycle = scope.previous(back) if back else scope
		rows.append({"from_date": cycle.from_date, "to_date": cycle.to_date, **totals(cycle.get_slips())})
	return {"rows": rows}


def journal_summary(scope: Scope) -> dict:
	"""Submitted salary slips against the accrual journal entries that booked them.

	When HRMS books payroll per employee (Payroll Settings), each slip's net pay is matched to that
	employee's payable line. When it books a run in one line, the run's slips are matched together: they
	are all Confirmed when their net pay adds up to what the journal credited to payroll payable."""
	slips = [s for s in scope.get_slips() if s.docstatus == 1]
	journals = {s.journal_entry for s in slips if s.journal_entry}
	# The books are read below without per-row checks, so only for users who may read journal entries
	lines = get_journal_lines(journals) if frappe.has_permission("Journal Entry", "read") else []
	payable_accounts = set(
		frappe.get_all(
			"Payroll Entry",
			filters={"name": ["in", list({s.payroll_entry for s in slips if s.payroll_entry}) or [""]]},
			pluck="payroll_payable_account",
		)
	)

	booked = JournalNet()
	expense = provisions = 0.0
	for line in lines:
		if line.root_type == "Expense":
			expense += flt(line.debit) - flt(line.credit)
		elif line.account in payable_accounts:
			booked.add(line)
		elif line.root_type == "Liability":
			provisions += flt(line.credit) - flt(line.debit)

	slip_net = defaultdict(float)
	for slip in slips:
		slip_net[slip.journal_entry] += flt(slip.net_pay)
	rows = [{**slip, **booked.match(slip, slip_net)} for slip in slips]

	earnings = sum(flt(s.gross_pay) for s in slips)
	deductions = sum(flt(s.total_deduction) for s in slips)
	statuses = [row["journal_status"] for row in rows]
	return {
		"summary": {
			"reconciled": statuses.count("Confirmed"),
			"discrepancies": statuses.count("Discrepancy"),
			"missing": statuses.count("Missing JV"),
			"salary_earnings": earnings,
			"journal_expense": expense,
			"earnings_variance": flt(expense - earnings, 2),
			"salary_deductions": deductions,
			"journal_provisions": provisions,
			"deductions_variance": flt(provisions - deductions, 2),
		},
		"journal_entries": sorted(journals),
		"rows": rows,
	}


class JournalNet:
	"""Net pay the accrual journals credited to payroll payable: per employee where the journal names
	the employee, and per journal entry in total."""

	def __init__(self):
		self.by_employee = defaultdict(float)
		self.by_journal = defaultdict(float)

	def add(self, line) -> None:
		amount = flt(line.credit) - flt(line.debit)
		self.by_journal[line.parent] += amount
		if line.party_type == "Employee" and line.party:
			self.by_employee[(line.parent, line.party)] += amount

	def match(self, slip, slip_net: dict) -> dict:
		if not slip.journal_entry:
			return {"journal_net": None, "variance": None, "journal_status": "Missing JV"}
		key = (slip.journal_entry, slip.employee)
		if key in self.by_employee:
			return self.result(self.by_employee[key], flt(slip.net_pay), per_employee=True)
		# Booked in one line for the whole run, so the run's slips stand or fall together
		return self.result(self.by_journal[slip.journal_entry], slip_net[slip.journal_entry], per_employee=False)

	def result(self, booked: float, expected: float, per_employee: bool) -> dict:
		variance = flt(booked - expected, 2)
		return {
			"journal_net": booked if per_employee else None,
			"variance": variance if per_employee or variance else None,
			"journal_status": "Confirmed" if not variance else "Discrepancy",
		}


def get_journal_lines(journals: set) -> list:
	if not journals:
		return []
	lines = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": ["in", list(journals)], "docstatus": 1},
		fields=["parent", "account", "debit", "credit", "party_type", "party"],
	)
	accounts = list({line.account for line in lines}) or [""]
	root_types = dict(frappe.get_all("Account", filters={"name": ["in", accounts]}, fields=["name", "root_type"], as_list=True))
	for line in lines:
		line.root_type = root_types.get(line.account)
	return lines
