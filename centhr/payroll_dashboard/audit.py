"""Pre-check audit: what to fix before running payroll, per employee, and payroll holds."""

import frappe
from frappe import _
from frappe.utils import cint, fmt_money, getdate

from centhr.payroll_dashboard import processing, reminders
from centhr.payroll_dashboard.attendance import AttendanceSummary
from centhr.payroll_dashboard.confidential import RULE
from centhr.payroll_dashboard.scope import Scope

# Shown as cards in this order; "status" is the employee count, the rest are checks
CHECKS = [
	("structure_missing", _("Missing Salary Structure")),
	("structure_inactive", _("Inactive Salary Structure")),
	("joiners", _("New Joiners")),
	("leave", _("Pending Leave Applications")),
	("attendance", _("Attendance & Absences")),
	("negative", _("Negative Salary Safeguard")),
	("dimensions", _("Accounting Dimensions")),
	("bank", _("Bank Details")),
]
# HRMS has no open-ended withholding, so "until released" is this many monthly cycles
UNTIL_RELEASED_CYCLES = 60
SAVEPOINT = "payroll_hold"


class PayrollAudit:
	def __init__(self, scope: Scope):
		self.scope = scope

	def run(self) -> dict:
		rows = [frappe._dict(r) for r in self.scope.get_employees()]
		names = [r.name for r in rows]
		attendance = AttendanceSummary(self.scope).summarize(rows)
		pending_leave = self.get_pending_leave(names)
		no_dimensions = self.get_missing_dimensions(names)
		holds = self.get_holds(names)
		reminded = reminders.get_last_sent(names, self.scope)
		self.advance_deductions = processing.get_advance_deductions(
			[r.salary_slip for r in rows if r.salary_slip]
		)

		for row in rows:
			row.attendance = attendance[row.name]
			row.issues = self.find_issues(row, pending_leave, no_dimensions)
			row.update(describe_hold(holds.get(row.name)))
			row.reminded_on = reminded.get(row.name)

		cards = [
			{
				"key": "status",
				"label": _("Employee Status"),
				"count": sum(r.status == "Active" for r in rows),
				"info": True,
			}
		]
		for key, label in CHECKS:
			cards.append({"key": key, "label": label, "count": sum(key in r.issues for r in rows)})
		cards.append({"key": "hold", "label": _("On Hold"), "count": sum(bool(r.hold) for r in rows)})
		return {"cards": cards, "rows": rows, "auto_attendance": self.has_auto_attendance()}

	def has_auto_attendance(self) -> bool:
		"""Whether a salary structure in scope has its attendance marked automatically."""
		return bool(
			frappe.db.exists(RULE, {"auto_attendance": 1, "disabled": 0, **self.scope.company_filter})
		)

	def describe_negative(self, row) -> str:
		"""An advance deduction larger than the salary is the usual cause, so it is named. The
		amounts are left as they are: HR decides whether to spread the recovery."""
		deducted = self.advance_deductions.get(row.salary_slip)
		if not deducted:
			return _("Net pay is zero or negative")
		return _("Net pay is zero or negative; {0} is deducted to recover advances").format(
			fmt_money(deducted, currency=row.currency)
		)

	def find_issues(self, row, pending_leave: dict, no_dimensions: dict) -> dict:
		"""Issue key -> short explanation, for the checks this employee fails."""
		issues = {}
		joined = (
			row.date_of_joining and self.scope.from_date <= getdate(row.date_of_joining) <= self.scope.to_date
		)
		if row.status == "Active" and not row.assignment:
			issues["structure_missing"] = _("No salary structure")
		elif row.structure_inactive:
			issues["structure_inactive"] = _("Salary structure {0} is inactive").format(row.salary_structure)
		if joined and not row.assignment:
			issues["joiners"] = _("Joined this cycle without a salary structure")
		if row.name in pending_leave:
			issues["leave"] = _("{0} leave application(s) awaiting approval").format(pending_leave[row.name])
		attendance = describe_attendance(row.attendance)
		if attendance:
			issues["attendance"] = attendance
		if row.salary_slip and (row.net_pay or 0) <= 0:
			issues["negative"] = self.describe_negative(row)
		if row.name in no_dimensions:
			issues["dimensions"] = _("Missing: {0}").format(", ".join(no_dimensions[row.name]))
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

	def get_missing_dimensions(self, employees: list[str]) -> dict[str, list[str]]:
		"""What payroll books a salary by and the employee lacks: department, channel, and the payroll
		cost center, which HRMS takes from the employee or else from the department."""
		if not employees:
			return {}
		with_channel = uses_channels()
		fields = ["name", "department", "payroll_cost_center", *(["channel"] if with_channel else [])]
		rows = frappe.get_all("Employee", filters={"name": ["in", employees]}, fields=fields)
		departments = {r.department for r in rows if r.department and not r.payroll_cost_center}
		with_center = set(
			frappe.get_all(
				"Department",
				filters={"name": ["in", list(departments) or [""]], "payroll_cost_center": ["is", "set"]},
				pluck="name",
			)
		)
		missing = {}
		for row in rows:
			lacks = [
				label
				for label, has in (
					(_("department"), row.department),
					(_("channel"), row.channel or not with_channel),
					(_("payroll cost center"), row.payroll_cost_center or row.department in with_center),
				)
				if not has
			]
			if lacks:
				missing[row.name] = lacks
		return missing

	def get_holds(self, employees: list[str]) -> dict:
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
			fields=[
				"employee",
				"name",
				"reason_for_withholding_salary",
				"from_date",
				"to_date",
				"number_of_withholding_cycles",
				"owner",
			],
		)
		return {r.employee: r for r in rows}


def describe_attendance(attendance: dict) -> str | None:
	"""Days the cycle still waits for: not marked, absent, or in a request nobody approved yet."""
	parts = [
		text.format(int(attendance[key]))
		for key, text in (
			("unmarked", _("{0} unmarked")),
			("absent", _("{0} absent")),
			("pending_leave", _("{0} in open leave applications")),
			("pending_request", _("{0} in open attendance requests")),
		)
		if attendance[key]
	]
	return ", ".join(parts) or None


def describe_hold(hold) -> dict:
	if not hold:
		return {"hold": None, "hold_reason": None}
	cycles = cint(hold.number_of_withholding_cycles) or 1
	return {
		"hold": hold.name,
		"hold_reason": hold.reason_for_withholding_salary,
		"hold_from": hold.from_date,
		"hold_to": hold.to_date,
		"hold_cycles": cycles,
		"hold_until_released": cycles >= UNTIL_RELEASED_CYCLES,
		"hold_by": frappe.db.get_value("User", hold.owner, "full_name") or hold.owner,
	}


def uses_channels() -> bool:
	"""Employees are only asked for a channel on a site that has channels."""
	return frappe.get_meta("Employee").has_field("channel") and bool(
		frappe.db.exists("Channel", {"disabled": 0})
	)


def set_hold(employee: str, scope: Scope, reason: str | None = None, cycles: int | None = 1) -> str:
	"""Withholds the employee's salary from this cycle on: for `cycles` pay cycles, or until it is
	released when `cycles` is 0. The reason is kept on the Salary Withholding."""
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Say why this salary is put on hold."), title=_("Reason Missing"))
	cycles = cint(cycles)
	if cycles < 0 or cycles > UNTIL_RELEASED_CYCLES:
		frappe.throw(_("Hold a salary for 1 to {0} pay cycles.").format(UNTIL_RELEASED_CYCLES))
	doc = frappe.get_doc(
		{
			"doctype": "Salary Withholding",
			"employee": employee,
			"from_date": scope.from_date,
			"payroll_frequency": "Monthly",
			"number_of_withholding_cycles": cycles or UNTIL_RELEASED_CYCLES,
			"reason_for_withholding_salary": reason,
		}
	).insert()
	doc.submit()
	return doc.name


def release_hold(withholding: str):
	frappe.get_doc("Salary Withholding", withholding).cancel()


def release_holds(withholdings: list[str]) -> dict:
	"""Release several holds; one that cannot be released does not stop the others."""
	done, failed = [], []
	for name in withholdings:
		frappe.db.savepoint(SAVEPOINT)
		try:
			release_hold(name)
			done.append(name)
		except Exception as e:
			frappe.db.rollback(save_point=SAVEPOINT)
			failed.append({"name": name, "error": frappe.utils.strip_html(str(e))})
	frappe.clear_messages()
	return {"done": done, "failed": failed}
