"""The OmniRetail leave policy, one rule per leave type.

Leave Type settings that HRMS already supports (holidays, carry forward) are applied by setup.py;
the rest is enforced by application.py (leave applications) and allocation.py (yearly credit, accrual).
"""

from dataclasses import dataclass

import frappe
from frappe.utils import getdate

ANNUAL = "Annual Leave"
CASUAL = "Casual Leave"
MATERNITY = "Maternity Leave"
PATERNITY = "Paternity Leave"
SICK = "Sick Leave"
ADOPTION = "Adoption Leave"
COMPASSIONATE = "Compassionate Leave"

# Credited on Jan 1 so Sick Leave has no practical limit; employees apply as often as they need
FULL_YEAR = 365


@dataclass(frozen=True)
class LeaveRule:
	# Days credited on Jan 1; None for Annual Leave, which accrues monthly by cadre
	yearly_days: float | None
	include_holidays: bool
	confirmed_only: bool = False
	gender: str | None = None
	# Applied in advance only: the leave cannot start before the application date
	advance_only: bool = False
	# Days between applying (and the final approval) and the first day of leave
	notice_days: int = 0
	# Leave types this one may be taken next to; None allows any, () allows none
	combines_with: tuple[str, ...] | None = ()
	# Taken only once this leave type's balance is used up
	after_exhausting: str | None = None
	# The leave may run into the next year and is charged in full to the year it starts in
	overflows_year: bool = False
	# Longer leaves need a medical certificate attached
	certificate_after_days: float | None = None
	carry_forward_days: float = 0
	child_rule: str | None = None


RULES: dict[str, LeaveRule] = {
	ANNUAL: LeaveRule(
		yearly_days=None,
		include_holidays=False,
		confirmed_only=True,
		advance_only=True,
		combines_with=None,
		carry_forward_days=5,
	),
	CASUAL: LeaveRule(
		yearly_days=5,
		include_holidays=False,
		confirmed_only=True,
		advance_only=True,
		after_exhausting=ANNUAL,
	),
	MATERNITY: LeaveRule(
		yearly_days=112,
		include_holidays=True,
		confirmed_only=True,
		gender="Female",
		advance_only=True,
		# Only with Annual Leave applied before the maternity leave
		combines_with=(ANNUAL,),
		overflows_year=True,
	),
	PATERNITY: LeaveRule(
		yearly_days=14,
		include_holidays=True,
		confirmed_only=True,
		gender="Male",
		advance_only=True,
		overflows_year=True,
		child_rule="birth",
	),
	SICK: LeaveRule(yearly_days=FULL_YEAR, include_holidays=False, certificate_after_days=3),
	ADOPTION: LeaveRule(
		yearly_days=60,
		include_holidays=True,
		confirmed_only=True,
		gender="Female",
		advance_only=True,
		notice_days=30,
		overflows_year=True,
		child_rule="adoption",
	),
	COMPASSIONATE: LeaveRule(yearly_days=5, include_holidays=False, overflows_year=True),
}

# Paternity leave ends within this many days of the birth; adoption needs a child this young (months)
PATERNITY_WINDOW_DAYS = 30
ADOPTION_MAX_CHILD_AGE_MONTHS = 6
# Carried forward Annual Leave is used by the end of the first quarter
CARRY_FORWARD_EXPIRY = (3, 31)


def get_rule(leave_type: str) -> LeaveRule | None:
	return RULES.get(leave_type)


def is_confirmed(employee: frappe._dict, on_date) -> bool:
	"""Confirmed (and so permanent) from the Final Confirmation Date."""
	return bool(employee.final_confirmation_date) and getdate(employee.final_confirmation_date) <= getdate(on_date)


def is_eligible(rule: LeaveRule, employee: frappe._dict, on_date) -> bool:
	if rule.confirmed_only and not is_confirmed(employee, on_date):
		return False
	return not rule.gender or employee.gender == rule.gender


def get_employee(name: str) -> frappe._dict:
	return frappe.db.get_value(
		"Employee", name, ["name", "gender", "grade", "final_confirmation_date", "date_of_joining", "company"], as_dict=True
	)
