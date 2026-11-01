"""Leave allocations of the leave policy: the Jan 1 credit of each leave type and the monthly Annual Leave accrual.

Both run daily and skip what is already done, so a missed day catches up and new confirmations get their leave.
"""

from datetime import date

import frappe
from frappe.utils import add_days, add_months, date_diff, flt, get_first_day, get_last_day, getdate, today
from hrms.hr.utils import create_additional_leave_ledger_entry, get_holidays_for_employee

from centhr.leave_policy.rules import ANNUAL, CARRY_FORWARD_EXPIRY, RULES, get_employee, is_confirmed, is_eligible

# Attendance that counts as a day worked; leave counts too unless it is unpaid
WORKED = {"Present": 1, "Work From Home": 1, "Half Day": 0.5, "On Leave": 1}


def allocate_yearly_leaves():
	YearlyAllocator(getdate(today())).run()


def accrue_annual_leave():
	"""Credits last month, once its attendance is complete."""
	AnnualLeaveAccrual(get_first_day(add_months(getdate(today()), -1))).run()


class YearlyAllocator:
	"""Gives every eligible employee each policy leave type for the year, from Jan 1 (or their joining date)."""

	def __init__(self, on_date: date):
		self.on_date = on_date
		self.year_start = date(on_date.year, 1, 1)
		self.year_end = date(on_date.year, 12, 31)

	def run(self):
		for name in frappe.get_all("Employee", filters={"status": "Active"}, pluck="name"):
			employee = get_employee(name)
			for leave_type, rule in RULES.items():
				if is_eligible(rule, employee, self.on_date) and not self.has_allocation(name, leave_type):
					run_logged(self.allocate, employee, leave_type, rule)

	def allocate(self, employee, leave_type: str, rule):
		from_date = max(self.year_start, getdate(employee.date_of_joining or self.year_start))
		# HRMS refuses more days than the allocation period has, e.g. for someone joining in December
		days = min(rule.yearly_days or 0, date_diff(self.year_end, from_date) + 1)
		allocation = frappe.get_doc(
			{
				"doctype": "Leave Allocation",
				"employee": employee.name,
				"leave_type": leave_type,
				"from_date": from_date,
				"to_date": self.year_end,
				"new_leaves_allocated": days,
				"carry_forward": 1 if rule.carry_forward_days else 0,
				"description": "Leave policy: yearly allocation",
			}
		)
		allocation.insert(ignore_permissions=True)
		allocation.submit()
		if rule.carry_forward_days:
			self.set_carry_forward_expiry(allocation)

	def set_carry_forward_expiry(self, allocation):
		"""HRMS expires carried forward leave after a number of days; the policy says the end of March."""
		month, day = CARRY_FORWARD_EXPIRY
		frappe.db.set_value(
			"Leave Ledger Entry",
			{"transaction_name": allocation.name, "is_carry_forward": 1, "docstatus": 1},
			"to_date",
			date(self.year_start.year, month, day),
		)

	def has_allocation(self, employee: str, leave_type: str) -> bool:
		return bool(
			frappe.db.exists(
				"Leave Allocation",
				{
					"employee": employee,
					"leave_type": leave_type,
					"docstatus": 1,
					"from_date": ["<=", self.year_end],
					"to_date": [">=", self.year_start],
				},
			)
		)


class AnnualLeaveAccrual:
	"""Annual Leave for one month: days worked × (cadre days / 12) / working days in the month.
	Days worked are present days plus paid leave, from the confirmation date on."""

	def __init__(self, month_start: date):
		self.start = getdate(month_start)
		self.end = get_last_day(self.start)
		self.unpaid_leave_types = set(frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name"))

	def run(self):
		for allocation in self.get_allocations():
			if not self.already_accrued(allocation.name):
				run_logged(self.accrue, allocation)

	def accrue(self, allocation):
		days = self.get_accrual(get_employee(allocation.employee))
		if days <= 0:
			return
		doc = frappe.get_doc("Leave Allocation", allocation.name)
		doc.db_set("total_leaves_allocated", flt(doc.total_leaves_allocated) + days, update_modified=False)
		# Dated at month end, which also marks the month as done
		create_additional_leave_ledger_entry(doc, days, self.end)

	def get_accrual(self, employee) -> float:
		cadre_days = flt(frappe.db.get_value("Employee Grade", employee.grade, "annual_leave_days")) if employee.grade else 0
		if not cadre_days or not is_confirmed(employee, self.end):
			return 0

		holidays = self.get_holidays(employee.name)
		working_days = sum(1 for day in self.days(self.start) if day not in holidays)
		if not working_days:
			return 0
		counted_from = max(self.start, getdate(employee.final_confirmation_date))
		worked = min(self.get_days_worked(employee.name, counted_from, holidays), working_days)
		return flt(worked * (cadre_days / 12) / working_days, 2)

	def get_days_worked(self, employee: str, counted_from: date, holidays: set) -> float:
		rows = frappe.get_all(
			"Attendance",
			filters={"employee": employee, "docstatus": 1, "attendance_date": ["between", [counted_from, self.end]]},
			fields=["attendance_date", "status", "leave_type"],
		)
		return sum(self.day_value(row) for row in rows if getdate(row.attendance_date) not in holidays)

	def day_value(self, row) -> float:
		paid_leave = row.leave_type and row.leave_type not in self.unpaid_leave_types
		if row.status == "On Leave":
			return 1 if paid_leave else 0
		if row.status == "Half Day" and paid_leave:
			return 1
		return WORKED.get(row.status, 0)

	def get_allocations(self) -> list:
		return frappe.get_all(
			"Leave Allocation",
			filters={"leave_type": ANNUAL, "docstatus": 1, "from_date": ["<=", self.end], "to_date": [">=", self.end]},
			fields=["name", "employee"],
		)

	def already_accrued(self, allocation: str) -> bool:
		return bool(
			frappe.db.exists(
				"Leave Ledger Entry",
				{
					"transaction_name": allocation,
					"transaction_type": "Leave Allocation",
					"from_date": self.end,
					"is_carry_forward": 0,
					"leaves": [">", 0],
					"docstatus": 1,
				},
			)
		)

	def get_holidays(self, employee: str) -> set:
		rows = get_holidays_for_employee(employee, self.start, self.end, raise_exception=False)
		return {getdate(row.holiday_date) for row in rows}

	def days(self, day: date):
		while day <= self.end:
			yield day
			day = add_days(day, 1)


def run_logged(method, *args):
	"""One employee's failure is logged and rolled back without stopping the others."""
	frappe.db.savepoint("leave_policy")
	try:
		method(*args)
	except Exception:
		frappe.db.rollback(save_point="leave_policy")
		frappe.log_error(title=f"Leave policy: {method.__qualname__} failed")
