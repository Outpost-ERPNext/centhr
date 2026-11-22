"""Attendance of each employee in the pay cycle, as payroll will count it."""

from collections import defaultdict

import frappe
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from frappe.utils import add_days, getdate, today

from centhr.payroll_dashboard.scope import Scope

COUNTED = ("present", "work_from_home", "half_day", "paid_leave", "unpaid_leave", "absent")
# Days without attendance that a request covers; they wait for an approver, not for the employee
PENDING = ("pending_leave", "pending_request")


class AttendanceSummary:
	"""Working days are the cycle's days without holidays, within the employee's joining and leaving dates.
	Days still to come are not counted as unmarked, and neither are days in a leave application or an
	attendance request that still waits for approval."""

	def __init__(self, scope: Scope):
		self.scope = scope
		self.until = min(scope.to_date, getdate(today()))
		self.unpaid_types = set(frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name"))
		self.holiday_cache: dict[str, set] = {}

	def summarize(self, employees: list) -> dict[str, dict]:
		"""Per employee name; `employees` rows need name, date_of_joining and relieving_date."""
		names = [e.name for e in employees]
		marks = self.get_marks(names)
		pending = self.get_pending(names)
		return {
			e.name: self.summarize_one(e, marks.get(e.name, {}), pending.get(e.name, {})) for e in employees
		}

	def summarize_one(self, employee, marks: dict, pending: dict) -> dict:
		holidays = self.get_holidays(employee.name)
		start = max(self.scope.from_date, getdate(employee.date_of_joining or self.scope.from_date))
		end = min(self.scope.to_date, getdate(employee.relieving_date or self.scope.to_date))
		working = [d for d in days_between(start, end) if d not in holidays]

		counts = dict.fromkeys(COUNTED, 0.0)
		for day in working:
			kind = marks.get(day)
			if kind:
				counts[kind] += 1
		waiting = dict.fromkeys(PENDING, 0)
		unmarked = 0
		for day in working:
			if day > self.until or day in marks:
				continue
			if day in pending:
				waiting[pending[day]] += 1
			else:
				unmarked += 1
		paid_days = counts["present"] + counts["work_from_home"] + counts["paid_leave"] + counts["half_day"] * 0.5
		return {
			**counts,
			**waiting,
			"working_days": len(working),
			"unmarked": unmarked,
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

	def get_pending(self, employees: list[str]) -> dict[str, dict]:
		"""Each employee's days in an open leave application or a draft attendance request, as
		{date: kind}. A day in both counts as leave."""
		pending: dict[str, dict] = defaultdict(dict)
		if not employees:
			return pending
		for kind, doctype, extra in (
			("pending_request", "Attendance Request", {}),
			("pending_leave", "Leave Application", {"status": "Open"}),
		):
			rows = frappe.get_all(
				doctype,
				filters={
					"employee": ["in", employees],
					"docstatus": 0,
					"from_date": ["<=", self.scope.to_date],
					"to_date": [">=", self.scope.from_date],
					**extra,
				},
				fields=["employee", "from_date", "to_date"],
			)
			for row in rows:
				start, end = max(row.from_date, self.scope.from_date), min(row.to_date, self.scope.to_date)
				pending[row.employee].update(dict.fromkeys(days_between(start, end), kind))
		return pending

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
