import frappe
from frappe.utils import add_days, add_months, cstr, date_diff, getdate
from hrms.hr.utils import get_holidays_for_employee

MAX_EMPLOYEES = 50
MAX_DAYS = 62


@frappe.whitelist()
def get_holidays_for_employees(employees: list[str] | str, from_date: str, to_date: str) -> dict:
	"""Holiday dates (weekly offs included) per employee, from each one's Holiday List Assignment.
	The attendance register uses this to shade non-working days. HRMS has no batch method for it."""
	employees = frappe.parse_json(employees) if isinstance(employees, str) else employees
	if len(employees) > MAX_EMPLOYEES or date_diff(to_date, from_date) > MAX_DAYS:
		frappe.throw(
			frappe._("Ask for at most {0} employees and {1} days at a time.").format(MAX_EMPLOYEES, MAX_DAYS)
		)

	result = {}
	for employee in employees:
		if not frappe.has_permission("Employee", "read", employee):
			continue
		holidays = get_holidays_for_employee(employee, from_date, to_date, raise_exception=False)
		result[employee] = {cstr(h.holiday_date): bool(h.weekly_off) for h in holidays}
	return result


@frappe.whitelist()
def get_payroll_cycle(company: str, date: str) -> dict | None:
	"""The company's payroll period dates around `date`, so attendance views follow its pay cycle.

	Uses the part of the company's Payroll Period (see get_cycles) that contains the date.
	Returns None when no Payroll Period or part contains it."""
	date = getdate(date)
	periods = frappe.get_list(
		"Payroll Period",
		filters={"company": company, "start_date": ("<=", date), "end_date": (">=", date)},
		fields=["name", "start_date", "end_date"],
		limit=1,
	)
	if not periods:
		return None

	period = periods[0]
	cycle = next((c for c in get_cycles(period) if c.start_date <= date <= c.end_date), None)
	if not cycle:
		return None

	return {"payroll_period": period.name, "from_date": cycle.start_date, "to_date": cycle.end_date}


@frappe.whitelist()
def get_payroll_years(company: str) -> list[dict]:
	"""The company's Payroll Periods (one per payroll year), newest first, each with its parts
	(see get_cycles), so attendance views can pick a year and then a month of it."""
	years = frappe.get_list(
		"Payroll Period",
		filters={"company": company},
		fields=["name", "start_date", "end_date"],
		order_by="start_date desc",
	)
	result = []
	for year in years:
		result.append(
			{
				"payroll_period": year.name,
				"from_date": year.start_date,
				"to_date": year.end_date,
				"periods": [{"from_date": c.start_date, "to_date": c.end_date} for c in get_cycles(year)],
			}
		)
	return result


def get_cycles(period) -> list:
	"""The parts of a Payroll Period, in date order: its Payroll Period Date rows, else the whole period
	when it is short enough to be one cycle, else monthly parts. HRMS hides the rows table on the
	Payroll Period form, so year-long periods normally have no rows and are split by month."""
	rows = frappe.get_all(
		"Payroll Period Date",
		filters={"parent": period.name, "parenttype": "Payroll Period"},
		fields=["start_date", "end_date"],
		order_by="start_date asc",
	)
	if rows:
		return rows
	if date_diff(period.end_date, period.start_date) <= MAX_DAYS:
		return [period]
	return split_into_months(period.start_date, period.end_date)


def split_into_months(start, end) -> list:
	"""Monthly parts from `start` to `end`, each starting on the same day of the month as `start`.
	A period from 20 Jan gives 20 Jan – 19 Feb, 20 Feb – 19 Mar and so on; the last part stops at `end`."""
	start, end = getdate(start), getdate(end)
	cycles = []
	part_start = start
	while part_start <= end:
		# Counted from `start` each time, so a start day of 31 comes back after a short month
		next_start = getdate(add_months(start, len(cycles) + 1))
		part_end = min(getdate(add_days(next_start, -1)), end)
		cycles.append(frappe._dict(start_date=part_start, end_date=part_end))
		part_start = next_start
	return cycles
