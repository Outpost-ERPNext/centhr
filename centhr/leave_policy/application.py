"""Leave Application checks of the leave policy. HRMS has already checked balance, overlap and dates."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, date_diff, formatdate, get_datetime, getdate, today
from hrms.hr.doctype.leave_application.leave_application import get_leave_balance_on
from hrms.hr.utils import get_holidays_for_employee

from centhr.leave_policy.rules import (
	ADOPTION_MAX_CHILD_AGE_MONTHS,
	ANNUAL,
	MATERNITY,
	PATERNITY_WINDOW_DAYS,
	get_employee,
	get_rule,
	is_confirmed,
)

# Leave applications this close before or after are checked for being taken back to back
ADJACENT_WINDOW_DAYS = 14


class LeaveApplicationPolicy:
	def __init__(self, doc):
		self.doc = doc
		self.rule = get_rule(doc.leave_type)
		self.employee = get_employee(doc.employee)
		self.applied_on = getdate(doc.posting_date or today())

	def validate_request(self):
		"""Who may apply and when. Runs before HRMS's checks, so an ineligible employee hears why."""
		if not self.rule or not self.is_checked():
			return
		self.check_eligibility()
		self.check_child()
		if self.dates_changed():
			self.check_advance()
			self.check_notice(self.applied_on)

	def validate_leave(self):
		"""Checks that need the leave days and balances HRMS works out."""
		if not self.is_checked():
			return
		if self.rule:
			self.check_certificate()
			self.check_exhausted()
		self.check_combination()

	def is_checked(self) -> bool:
		"""Rejected and cancelled applications are no longer checked."""
		return self.doc.status != "Rejected" and self.doc.docstatus != 2

	def validate_approval(self):
		"""The final approval also has to come early enough before the leave starts."""
		if self.rule and self.doc.status == "Approved":
			self.check_notice(getdate(today()), approval=True)

	def check_eligibility(self):
		rule, employee = self.rule, self.employee
		if rule.confirmed_only and not is_confirmed(employee, self.doc.from_date):
			frappe.throw(_("{0} is only for confirmed employees.").format(self.doc.leave_type))
		if rule.gender and employee.gender != rule.gender:
			frappe.throw(_("{0} is only for {1} employees.").format(self.doc.leave_type, _(rule.gender).lower()))

	def check_advance(self):
		if not self.rule.advance_only or getdate(self.doc.from_date) >= self.applied_on:
			return
		if self.may_backdate():
			return
		frappe.throw(_("{0} must be applied in advance; it cannot be backdated.").format(self.doc.leave_type))

	def check_notice(self, on_date, approval=False):
		days = self.rule.notice_days
		if not days or date_diff(self.doc.from_date, on_date) >= days:
			return
		message = (
			_("{0} must be approved at least {1} days before it starts.")
			if approval
			else _("{0} must be applied at least {1} days before it starts.")
		)
		frappe.throw(message.format(self.doc.leave_type, days))

	def check_exhausted(self):
		other = self.rule.after_exhausting
		if not other:
			return
		balance = get_leave_balance_on(self.doc.employee, other, self.doc.from_date)
		if balance > 0:
			frappe.throw(
				_("{0} can only be taken once {1} is used up. {2} days of {1} are left.").format(
					self.doc.leave_type, other, balance
				)
			)

	def check_child(self):
		rule_kind = self.rule.child_rule
		if not rule_kind:
			return
		birth = self.doc.get("child_date_of_birth")
		if not birth:
			frappe.throw(_("Enter the child's date of birth for {0}.").format(self.doc.leave_type))
		birth = getdate(birth)

		if rule_kind == "birth":
			last_day = add_days(birth, PATERNITY_WINDOW_DAYS)
			if getdate(self.doc.from_date) < birth or getdate(self.doc.to_date) > last_day:
				frappe.throw(
					_("{0} must be taken within {1} days of the birth, by {2}.").format(
						self.doc.leave_type, PATERNITY_WINDOW_DAYS, formatdate(last_day)
					)
				)
		elif add_months(birth, ADOPTION_MAX_CHILD_AGE_MONTHS) < self.applied_on:
			frappe.throw(
				_("{0} is only for a child of {1} months or younger.").format(
					self.doc.leave_type, ADOPTION_MAX_CHILD_AGE_MONTHS
				)
			)

	def check_certificate(self):
		limit = self.rule.certificate_after_days
		if limit and self.doc.total_leave_days > limit and not self.doc.get("leave_attachment"):
			frappe.throw(
				_("Attach a certificate from an authorised medical officer for {0} longer than {1} days.").format(
					self.doc.leave_type, limit
				)
			)

	def check_combination(self):
		"""Back-to-back leave of two types, with only holidays between them, is one combined leave."""
		for other in self.get_adjacent_applications():
			if not can_combine(self.doc.leave_type, other.leave_type, self.applied_before(other)):
				frappe.throw(
					_("{0} cannot be combined with {1} ({2}, {3} to {4}).").format(
						self.doc.leave_type,
						other.leave_type,
						other.name,
						formatdate(other.from_date),
						formatdate(other.to_date),
					)
				)

	def get_adjacent_applications(self) -> list:
		start, end = getdate(self.doc.from_date), getdate(self.doc.to_date)
		others = frappe.get_all(
			"Leave Application",
			filters={
				"employee": self.doc.employee,
				"name": ["!=", self.doc.name or ""],
				"docstatus": ["<", 2],
				"status": ["!=", "Rejected"],
				"to_date": [">=", add_days(start, -ADJACENT_WINDOW_DAYS)],
				"from_date": ["<=", add_days(end, ADJACENT_WINDOW_DAYS)],
			},
			fields=["name", "leave_type", "from_date", "to_date", "creation"],
		)
		holidays = self.get_holidays(add_days(start, -ADJACENT_WINDOW_DAYS), add_days(end, ADJACENT_WINDOW_DAYS))
		return [o for o in others if only_holidays_between(o, start, end, holidays)]

	def applied_before(self, other) -> bool:
		"""Whether `other` was applied for before this application."""
		return not self.doc.creation or get_datetime(other.creation) < get_datetime(self.doc.creation)

	def get_holidays(self, start, end) -> set:
		rows = get_holidays_for_employee(self.doc.employee, start, end, raise_exception=False)
		return {getdate(row.holiday_date) for row in rows}

	def dates_changed(self) -> bool:
		return self.doc.is_new() or self.doc.has_value_changed("from_date") or self.doc.has_value_changed("to_date")

	def may_backdate(self) -> bool:
		role = frappe.db.get_single_value("HR Settings", "role_allowed_to_create_backdated_leave_application")
		return bool(role) and role in frappe.get_roles()


def can_combine(leave_type: str, other_type: str, other_applied_first: bool) -> bool:
	"""Both rules must allow it. Maternity Leave takes Annual Leave only when the Annual Leave was applied first."""
	if {leave_type, other_type} == {MATERNITY, ANNUAL}:
		annual_first = other_applied_first if leave_type == MATERNITY else not other_applied_first
		if not annual_first:
			return False
	return permits(leave_type, other_type) and permits(other_type, leave_type)


def permits(leave_type: str, other_type: str) -> bool:
	allowed = allowed_with(leave_type)
	return allowed is None or other_type in allowed


def allowed_with(leave_type: str) -> tuple[str, ...] | None:
	rule = get_rule(leave_type)
	# Leave types outside the policy (Leave Without Pay, Compensatory Off) combine with anything
	return rule.combines_with if rule else None


def only_holidays_between(other, start, end, holidays: set) -> bool:
	"""`other` ends right before `start` or begins right after `end`, apart from holidays in the gap."""
	other_start, other_end = getdate(other.from_date), getdate(other.to_date)
	if other_end < start:
		gap_from, gap_to = add_days(other_end, 1), add_days(start, -1)
	elif other_start > end:
		gap_from, gap_to = add_days(end, 1), add_days(other_start, -1)
	else:
		return True
	day = getdate(gap_from)
	while day <= getdate(gap_to):
		if day not in holidays:
			return False
		day = add_days(day, 1)
	return True
