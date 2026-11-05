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
	"""Submitted salary slips against the accrual journal entries that booked them. Net pay is matched
	per employee when HRMS books payroll per employee (Payroll Settings); earnings and deductions in total."""
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

	booked_net = defaultdict(float)
	expense = provisions = 0.0
	for line in lines:
		if line.root_type == "Expense":
			expense += flt(line.debit) - flt(line.credit)
		elif line.account in payable_accounts:
			if line.party_type == "Employee" and line.party:
				booked_net[line.party] += flt(line.credit) - flt(line.debit)
		elif line.root_type == "Liability":
			provisions += flt(line.credit) - flt(line.debit)

	rows = [{**slip, **match_slip(slip, booked_net)} for slip in slips]
	earnings = sum(flt(s.gross_pay) for s in slips)
	deductions = sum(flt(s.total_deduction) for s in slips)
	return {
		"summary": {
			"reconciled": sum(r["journal_status"] == "Confirmed" for r in rows),
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


def match_slip(slip, booked_net: dict) -> dict:
	if not slip.journal_entry:
		return {"journal_net": None, "variance": None, "journal_status": "Not booked"}
	if slip.employee not in booked_net:
		# HRMS booked the run in one line, so only the totals can be matched
		return {"journal_net": None, "variance": None, "journal_status": "Booked in total"}
	variance = flt(booked_net[slip.employee] - flt(slip.net_pay), 2)
	return {"journal_net": booked_net[slip.employee], "variance": variance, "journal_status": "Confirmed" if not variance else "Discrepancy"}


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
