import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import flt, getdate
from hrms.hr.doctype.leave_application.leave_application import (
	get_leave_allocation_records,
	get_leave_balance_on,
	get_leaves_pending_approval_for_period,
	get_number_of_leave_days,
)

from centhr.overrides.leave_application import as_employee_user


def get_context(context):
	# do your magic here
	pass


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 10)
def get_employees(company: str) -> list[dict]:
	"""Employee ID options of the web form, labelled with the name so it can be searched."""
	employees = frappe.get_all(
		"Employee",
		filters={"company": company, "status": "Active"},
		fields=["name", "employee_name"],
	)
	# the ID keeps two employees with the same name apart
	options = [{"value": e.name, "label": f"{(e.employee_name or '').strip()} ({e.name})"} for e in employees]
	return sorted(options, key=lambda option: option["label"].lower())


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 10)
def get_leave_types(employee: str, date: str | None = None) -> list[dict]:
	"""Leave Type options of the web form: the employee's allocated leave types, then Leave Without Pay."""
	if not is_active_employee(employee):
		return []

	date = getdate(date)
	options = []
	for leave_type, allocation in get_leave_allocation_records(employee, date).items():
		balance = get_allocation_balance(employee, leave_type, date, allocation)
		options.append({"value": leave_type, "label": leave_type, "description": f"Balance: {balance:g}"})

	allocated = {option["value"] for option in options}
	for leave_type in frappe.get_all("Leave Type", filters={"is_lwp": 1}, pluck="name", order_by="name"):
		if leave_type not in allocated:
			options.append({"value": leave_type, "label": leave_type, "description": "Leave Without Pay"})
	return options


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 10)
def get_leave_balance(
	employee: str, leave_type: str, date: str | None = None, to_date: str | None = None
) -> dict:
	"""Leave Balance, Pending for Approval and Leave Days of the web form, as the Leave Application
	form in Desk shows them. insufficient is the check that HRMS throws on at save."""
	date = getdate(date)
	result = {"leave_balance": 0, "leaves_pending_approval": 0, "leave_days": 0, "insufficient": False}
	if not is_active_employee(employee) or not frappe.db.exists("Leave Type", leave_type):
		return result

	# HRMS checks that the session user may read the employee, which Guest cannot
	with as_employee_user(employee):
		return set_leave_balance(result, employee, leave_type, date, to_date)


def set_leave_balance(result: dict, employee: str, leave_type: str, date, to_date: str | None) -> dict:
	if to_date and getdate(to_date) >= date:
		result["leave_days"] = get_number_of_leave_days(employee, leave_type, date, getdate(to_date))

	allocation = get_leave_allocation_records(employee, date, leave_type).get(leave_type)
	if allocation:
		result["leave_balance"] = get_allocation_balance(employee, leave_type, date, allocation)
		result["leaves_pending_approval"] = get_leaves_pending_approval_for_period(
			employee, leave_type, allocation.from_date, allocation.to_date
		)

	is_lwp, allow_negative = frappe.db.get_value("Leave Type", leave_type, ["is_lwp", "allow_negative"])
	if result["leave_days"] > 0 and not is_lwp and not allow_negative:
		available = get_leave_balance_on(
			employee,
			leave_type,
			date,
			getdate(to_date),
			consider_all_leaves_in_the_allocation_period=True,
			for_consumption=True,
		)
		result["available"] = flt(available.get("leave_balance_for_consumption"), 2)
		result["insufficient"] = result["available"] < result["leave_days"]
	return result


def get_allocation_balance(employee: str, leave_type: str, date, allocation) -> float:
	# HRMS checks that the session user may read the employee, which Guest cannot
	with as_employee_user(employee):
		return get_leave_balance_on(
			employee,
			leave_type,
			date,
			to_date=allocation.to_date,
			consider_all_leaves_in_the_allocation_period=True,
		)


def is_active_employee(employee: str) -> bool:
	return bool(frappe.db.exists("Employee", {"name": employee, "status": "Active"}))
