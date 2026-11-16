"""Who sees whose KPI Templates and KPI Results.

HR sees every employee, within the companies their user permissions allow. Everyone else sees their
own records and those of the employees who report to them directly, and can only fill in and submit
the results of those direct reports.
"""

import frappe

HR_ROLES = {"HR Manager", "HR User", "System Manager"}
READ_ONLY_TYPES = ("read", "select", "report", "print", "email", "export")


def get_permission_query_conditions(user: str | None = None, doctype: str | None = None) -> str | None:
	user = user or frappe.session.user
	if is_hr(user):
		return None

	employees = get_own_and_reports(user)
	if not employees:
		return "1=0"
	names = ", ".join(frappe.db.escape(employee) for employee in employees)
	return f"`tab{doctype}`.employee in ({names})"


def has_permission(doc, ptype: str | None = None, user: str | None = None) -> bool:
	"""Frappe v16 reads anything but True as a denial; the role permissions are checked besides this."""
	user = user or frappe.session.user
	if is_hr(user) or not doc.employee:
		return True

	own = get_employee(user)
	if doc.employee in get_direct_reports(own):
		return True
	# Nobody fills in or submits their own result
	return doc.employee == own and ptype in READ_ONLY_TYPES


def is_hr(user: str) -> bool:
	return user == "Administrator" or bool(HR_ROLES.intersection(frappe.get_roles(user)))


def get_own_and_reports(user: str) -> list[str]:
	own = get_employee(user)
	return [own, *get_direct_reports(own)] if own else []


def get_employee(user: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def get_direct_reports(employee: str | None) -> list[str]:
	if not employee:
		return []
	return frappe.get_all("Employee", filters={"reports_to": employee}, pluck="name")
