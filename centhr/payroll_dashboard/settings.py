"""Payroll settings of one company: its pay cycle and whether payroll recovers overdue advances."""

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, today

MAX_START_DAY = 28
YEARS_SHOWN = 6
MANAGER_ROLES = {"HR Manager", "System Manager"}


def get_settings(company: str) -> dict:
	frappe.has_permission("Company", "read", doc=company, throw=True)
	start_day, auto_recover = frappe.db.get_value(
		"Company", company, ["payroll_cycle_start_day", "auto_recover_advances"]
	)
	return {
		"company": company,
		"start_day": cint(start_day) or 1,
		"auto_recover_advances": cint(auto_recover),
		"recovery_component": frappe.db.get_single_value("CentHr Settings", "iou_salary_component"),
		"can_edit": bool(MANAGER_ROLES.intersection(frappe.get_roles())),
	}


def save_settings(company: str, start_day: int, auto_recover_advances: bool) -> dict:
	frappe.only_for(list(MANAGER_ROLES))
	frappe.has_permission("Company", "read", doc=company, throw=True)
	start_day = cint(start_day) or 1
	if not 1 <= start_day <= MAX_START_DAY:
		frappe.throw(_("The cycle start day must be between 1 and {0}.").format(MAX_START_DAY))
	if auto_recover_advances and not frappe.db.get_single_value("CentHr Settings", "iou_salary_component"):
		frappe.throw(
			_("Set the IOU Recovery Salary Component in CentHr Settings before turning on advance recovery."),
			title=_("Recovery Component Missing"),
		)
	# HR runs payroll without rights on the Company record itself
	frappe.db.set_value(
		"Company",
		company,
		{"payroll_cycle_start_day": start_day, "auto_recover_advances": cint(auto_recover_advances)},
	)
	return get_settings(company)


def get_start_day(company: str | None) -> int:
	"""The company's cycle start day, 0 when it follows calendar months or its Payroll Period."""
	if not company:
		return 0
	day = cint(frappe.db.get_value("Company", company, "payroll_cycle_start_day"))
	return day if 1 < day <= MAX_START_DAY else 0


def get_cycle(start_day: int, day: date | str) -> tuple[date, date]:
	"""The pay cycle that contains `day`: from `start_day` of one month to the day before it in the next."""
	day = getdate(day)
	start = day.replace(day=start_day)
	if day.day < start_day:
		start = getdate(add_months(start, -1))
	return start, getdate(add_days(add_months(start, 1), -1))


def get_years(start_day: int) -> list[dict]:
	"""Payroll years, newest first. A cycle belongs to the month it ends in, so with start day 20 the
	year 2026 runs from 20 Dec 2025 to 19 Dec 2026."""
	current = getdate(today()).year
	years = []
	for year in range(current + 1, current + 1 - YEARS_SHOWN, -1):
		periods = [get_cycle(start_day, date(year, month, 1)) for month in range(1, 13)]
		years.append(
			{
				"label": str(year),
				"payroll_period": None,
				# Tells the page where these cycles come from, so it can say so
				"start_day": start_day,
				"from_date": periods[0][0],
				"to_date": periods[-1][1],
				"periods": [{"from_date": start, "to_date": end} for start, end in periods],
			}
		)
	return years
