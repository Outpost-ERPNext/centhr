"""Pre-check audit: what to fix before running payroll, per employee, and payroll holds."""

import frappe
from frappe import _

from centhr.api.salary_overview import SalaryOverview
from centhr.payroll_dashboard.attendance import AttendanceSummary
from centhr.payroll_dashboard.scope import Scope

# Shown as cards in this order; "status" is the employee count, the rest are checks
CHECKS = [
	("structure", _("Salary Structure Assignment")),
	("joiners", _("New Joiners")),
	("leave", _("Pending Leave Applications")),
	("attendance", _("Attendance & Absences")),
	("negative", _("Negative Salary Safeguard")),
	("dimensions", _("Accounting Dimensions")),
	("bank", _("Bank Details")),
]


class PayrollAudit:
	def __init__(self, scope: Scope):
		self.scope = scope

	def run(self) -> dict:
		rows = [frappe._dict(r) for r in SalaryOverview(self.scope.company, self.scope.from_date, self.scope.to_date).get_rows()]
		names = [r.name for r in rows]
		attendance = AttendanceSummary(self.scope).summarize(rows)
		pending_leave = self.get_pending_leave(names)
		no_cost_center = self.get_missing_cost_center(names)
		holds = self.get_holds(names)

		for row in rows:
			row.attendance = attendance[row.name]
			row.issues = self.find_issues(row, pending_leave, no_cost_center)
			row.hold = holds.get(row.name)

		cards = [{"key": "status", "label": _("Employee Status"), "count": sum(r.status == "Active" for r in rows), "info": True}]
		for key, label in CHECKS:
			cards.append({"key": key, "label": label, "count": sum(key in r.issues for r in rows)})
		return {"cards": cards, "rows": rows}

	def find_issues(self, row, pending_leave: dict, no_cost_center: set) -> dict:
		"""Issue key -> short explanation, for the checks this employee fails."""
		issues = {}
		joined = row.date_of_joining and self.scope.from_date <= frappe.utils.getdate(row.date_of_joining) <= self.scope.to_date
		if row.status == "Active" and not row.assignment:
			issues["structure"] = _("No salary structure")
		elif row.structure_inactive:
			issues["structure"] = _("Salary structure is inactive")
		if joined and not row.assignment:
			issues["joiners"] = _("Joined this cycle without a salary structure")
		if row.name in pending_leave:
			issues["leave"] = _("{0} leave application(s) awaiting approval").format(pending_leave[row.name])
		att = row.attendance
		if att["unmarked"] or att["absent"]:
			issues["attendance"] = _("{0} unmarked, {1} absent").format(int(att["unmarked"]), int(att["absent"]))
		if row.salary_slip and (row.net_pay or 0) <= 0:
			issues["negative"] = _("Net pay is zero or negative")
		if row.name in no_cost_center:
			issues["dimensions"] = _("No payroll cost center")
		if row.salary_mode == "Bank" and not row.bank_ac_no:
			issues["bank"] = _("Paid by bank without an account number")
		return issues

	def get_pending_leave(self, employees: list[str]) -> dict[str, int]:
		if not employees:
			return {}
		rows = frappe.get_all(
			"Leave Application",
			filters={
				"employee": ["in", employees],
				"docstatus": 0,
				"status": "Open",
				"from_date": ["<=", self.scope.to_date],
				"to_date": [">=", self.scope.from_date],
			},
			fields=["employee", {"COUNT": "*", "as": "count"}],
			group_by="employee",
		)
		return {r.employee: r.count for r in rows}

	def get_missing_cost_center(self, employees: list[str]) -> set:
		"""HRMS books salaries to the employee's payroll cost center, else the department's."""
		if not employees:
			return set()
		rows = frappe.get_all(
			"Employee", filters={"name": ["in", employees]}, fields=["name", "payroll_cost_center", "department"]
		)
		departments = {r.department for r in rows if r.department and not r.payroll_cost_center}
		with_center = set(
			frappe.get_all(
				"Department", filters={"name": ["in", list(departments) or [""]], "payroll_cost_center": ["is", "set"]}, pluck="name"
			)
		)
		return {r.name for r in rows if not r.payroll_cost_center and r.department not in with_center}

	def get_holds(self, employees: list[str]) -> dict[str, str]:
		"""Salary Withholdings covering the cycle; HRMS marks those employees' slips Withheld."""
		if not employees:
			return {}
		rows = frappe.get_all(
			"Salary Withholding",
			filters={
				"employee": ["in", employees],
				"docstatus": 1,
				"status": "Withheld",
				"from_date": ["<=", self.scope.to_date],
				"to_date": [">=", self.scope.from_date],
			},
			fields=["employee", "name"],
		)
		return {r.employee: r.name for r in rows}


def set_hold(employee: str, scope: Scope, reason: str | None = None) -> str:
	"""Withholds the employee's salary for this one cycle."""
	doc = frappe.get_doc(
		{
			"doctype": "Salary Withholding",
			"employee": employee,
			"from_date": scope.from_date,
			"payroll_frequency": "Monthly",
			"number_of_withholding_cycles": 1,
			"reason_for_withholding_salary": reason or _("Held from the Payroll Dashboard"),
		}
	).insert()
	doc.submit()
	return doc.name


def release_hold(withholding: str):
	frappe.get_doc("Salary Withholding", withholding).cancel()
