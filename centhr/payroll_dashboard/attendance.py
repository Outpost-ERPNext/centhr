"""Attendance of each employee in the pay cycle, as payroll will count it."""

from collections import defaultdict

import frappe
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from frappe.utils import add_days, getdate, today

from centhr.payroll_dashboard.scope import Scope

COUNTED = ("present", "work_from_home", "half_day", "paid_leave", "unpaid_leave", "absent")


class AttendanceSummary:
	"""Working days are the cycle's days without holidays, within the employee's joining and leaving dates.
	Days still to come are not counted as unmarked."""

	def __init__(self, scope: Scope):
		self.scope = scope
		self.until = min(scope.to_date, getdate(today()))
		self.unpaid_types = set(frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name"))
		self.holiday_cache: dict[str, set] = {}

	def summarize(self, employees: list) -> dict[str, dict]:
		"""Per employee name; `employees` rows need name, date_of_joining and relieving_date."""
		marks = self.get_marks([e.name for e in employees])
		return {e.name: self.summarize_one(e, marks.get(e.name, {})) for e in employees}

	def summarize_one(self, employee, marks: dict) -> dict:
		holidays = self.get_holidays(employee.name)
		start = max(self.scope.from_date, getdate(employee.date_of_joining or self.scope.from_date))
		end = min(self.scope.to_date, getdate(employee.relieving_date or self.scope.to_date))
		working = [d for d in days_between(start, end) if d not in holidays]

		counts = dict.fromkeys(COUNTED, 0.0)
		for day in working:
			kind = marks.get(day)
			if kind:
				counts[kind] += 1
		marked_until_today = sum(1 for d in working if d <= self.until and d in marks)
		due = sum(1 for d in working if d <= self.until)
		paid_days = counts["present"] + counts["work_from_home"] + counts["paid_leave"] + counts["half_day"] * 0.5
		return {
			**counts,
			"working_days": len(working),
			"unmarked": due - marked_until_today,
			"holidays": len([d for d in days_between(start, end) if d in holidays]),
			"paid_days": paid_days,
		}

	def get_marks(self, employees: list[str]) -> dict[str, dict]:
		"""Each employee's attendance as {date: kind}."""
		marks: dict[str, dict] = defaultdict(dict)
		if not employees:
			return marks
		rows = frappe.get_all(
			"Attendance",
			filters={
				"employee": ["in", employees],
				"docstatus": 1,
				"attendance_date": ["between", [self.scope.from_date, self.scope.to_date]],
			},
			fields=["employee", "attendance_date", "status", "leave_type"],
		)
		for row in rows:
			marks[row.employee][getdate(row.attendance_date)] = self.kind(row)
		return marks

	def kind(self, row) -> str:
		if row.status == "On Leave":
			return "unpaid_leave" if row.leave_type in self.unpaid_types else "paid_leave"
		return {"Present": "present", "Work From Home": "work_from_home", "Half Day": "half_day"}.get(row.status, "absent")

	def get_holidays(self, employee: str) -> set:
		holiday_list = get_holiday_list_for_employee(employee, raise_exception=False, as_on=self.scope.from_date)
		if not holiday_list:
			return set()
		if holiday_list not in self.holiday_cache:
			dates = frappe.get_all(
				"Holiday",
				filters={"parent": holiday_list, "holiday_date": ["between", [self.scope.from_date, self.scope.to_date]]},
				pluck="holiday_date",
			)
			self.holiday_cache[holiday_list] = {getdate(d) for d in dates}
		return self.holiday_cache[holiday_list]


def days_between(start, end):
	day = getdate(start)
	while day <= getdate(end):
		yield day
		day = add_days(day, 1)
