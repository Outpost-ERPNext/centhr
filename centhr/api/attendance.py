import frappe
from frappe.utils import cstr, date_diff, getdate
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

	Uses the Payroll Period of the company that contains the date: the row of its period dates
	(Payroll Period Date) that contains the date, or the whole Payroll Period when it has no rows
	and is short enough to be a single cycle. Returns None when the company has none."""
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
	rows = frappe.get_all(
		"Payroll Period Date",
		filters={
			"parent": period.name,
			"parenttype": "Payroll Period",
			"start_date": ("<=", date),
			"end_date": (">=", date),
		},
		fields=["start_date", "end_date"],
		order_by="start_date asc",
		limit=1,
	)
	if rows:
		cycle = rows[0]
	elif date_diff(period.end_date, period.start_date) <= MAX_DAYS:
		cycle = period
	else:
		return None

	return {"payroll_period": period.name, "from_date": cycle.start_date, "to_date": cycle.end_date}


@frappe.whitelist()
def get_payroll_years(company: str) -> list[dict]:
	"""The company's Payroll Periods (one per payroll year), newest first, each with its period dates,
	so attendance views can pick a year and then a month of it."""
	years = frappe.get_list(
		"Payroll Period",
		filters={"company": company},
		fields=["name", "start_date", "end_date"],
		order_by="start_date desc",
	)
	result = []
	for year in years:
		rows = frappe.get_all(
			"Payroll Period Date",
			filters={"parent": year.name, "parenttype": "Payroll Period"},
			fields=["start_date", "end_date"],
			order_by="start_date asc",
		)
		if not rows and date_diff(year.end_date, year.start_date) <= MAX_DAYS:
			rows = [year]
		result.append(
			{
				"payroll_period": year.name,
				"from_date": year.start_date,
				"to_date": year.end_date,
				"periods": [{"from_date": r.start_date, "to_date": r.end_date} for r in rows],
			}
		)
	return result
