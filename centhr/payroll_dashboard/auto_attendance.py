"""Automatic attendance: employees on a salary structure marked for it are Present on every working
day nobody recorded. The rules are Payroll Structure Rule documents."""

import frappe
from frappe.utils import get_first_day, get_last_day, getdate, today

from centhr.payroll_dashboard.attendance import AttendanceSummary, days_between
from centhr.payroll_dashboard.confidential import RULE
from centhr.payroll_dashboard.scope import Scope

SAVEPOINT = "auto_attendance"


class AutoAttendance:
	def __init__(self, scope: Scope):
		self.scope = scope
		self.until = min(scope.to_date, getdate(today()))
		self.summary = AttendanceSummary(scope)

	def run(self) -> dict:
		"""Mark Present where there is no attendance yet. Holidays, days outside the employee's time
		with the company, days to come and days in an open leave application or attendance request
		are left alone, and so is every day that has attendance of any kind."""
		employees = self.get_employees()
		names = [e.name for e in employees]
		marked = self.get_marked(names)
		pending = self.summary.get_pending(names)
		outcome = {"employees": len(employees), "created": 0, "skipped": 0}
		for employee in employees:
			taken = marked.get(employee.name, set()) | set(pending.get(employee.name, {}))
			for day in self.get_working_days(employee):
				if day not in taken:
					outcome["created" if self.mark(employee, day) else "skipped"] += 1
		return outcome

	def get_employees(self) -> list:
		"""Employees whose salary structure, as assigned by the end of the cycle, marks attendance."""
		structures = frappe.get_all(
			RULE,
			filters={"auto_attendance": 1, "disabled": 0, **self.scope.company_filter},
			pluck="salary_structure",
		)
		if not structures:
			return []
		latest = {}
		for row in frappe.get_all(
			"Salary Structure Assignment",
			filters={**self.scope.company_filter, "docstatus": 1, "from_date": ["<=", self.scope.to_date]},
			fields=["employee", "salary_structure"],
			order_by="from_date asc",
		):
			latest[row.employee] = row.salary_structure
		on_rule = [employee for employee, structure in latest.items() if structure in structures]
		return frappe.get_all(
			"Employee",
			filters={"name": ["in", on_rule or [""]]},
			or_filters=[["status", "=", "Active"], ["relieving_date", ">=", self.scope.from_date]],
			fields=["name", "company", "date_of_joining", "relieving_date"],
		)

	def get_marked(self, employees: list[str]) -> dict[str, set]:
		"""Days that have attendance, draft or submitted: none of them is touched."""
		marked: dict[str, set] = {}
		for row in frappe.get_all(
			"Attendance",
			filters={
				"employee": ["in", employees or [""]],
				"docstatus": ["!=", 2],
				"attendance_date": ["between", [self.scope.from_date, self.scope.to_date]],
			},
			fields=["employee", "attendance_date"],
		):
			marked.setdefault(row.employee, set()).add(getdate(row.attendance_date))
		return marked

	def get_working_days(self, employee) -> list:
		holidays = self.summary.get_holidays(employee.name)
		start = max(self.scope.from_date, getdate(employee.date_of_joining or self.scope.from_date))
		end = min(self.until, getdate(employee.relieving_date or self.until))
		return [day for day in days_between(start, end) if day not in holidays]

	def mark(self, employee, day) -> bool:
		"""HRMS has the last word: it refuses a duplicate and turns a day of approved leave into leave."""
		frappe.db.savepoint(SAVEPOINT)
		try:
			attendance = frappe.get_doc(
				{
					"doctype": "Attendance",
					"employee": employee.name,
					"company": employee.company,
					"attendance_date": day,
					"status": "Present",
				}
			)
			attendance.flags.ignore_permissions = True
			attendance.insert()
			attendance.submit()
			return True
		except frappe.ValidationError:
			frappe.db.rollback(save_point=SAVEPOINT)
			frappe.clear_messages()
			return False


def mark(scope: Scope) -> dict:
	"""The audit's action; the user needs the right to create attendance."""
	frappe.has_permission("Attendance", "create", throw=True)
	return AutoAttendance(scope).run()


def mark_current_cycles() -> None:
	"""Daily: mark the current pay cycle of every company that has an auto-attendance rule."""
	from centhr.api.attendance import get_payroll_cycle

	companies = frappe.get_all(
		RULE, filters={"auto_attendance": 1, "disabled": 0}, pluck="company", distinct=True
	)
	for company in filter(None, companies):
		# Without a pay cycle of its own, the company is paid by calendar month
		cycle = get_payroll_cycle(company, today()) or {
			"from_date": get_first_day(today()),
			"to_date": get_last_day(today()),
		}
		AutoAttendance(Scope.make(cycle["from_date"], cycle["to_date"], company)).run()
