import frappe
from frappe import _
from frappe.utils import now_datetime

from centhr.api.shift_assignment_tool import get_advanced_filters

DOCTYPE = "Bulk Salary Structure Assignment"

# The HRMS tool runs up to this many assignments in the request and queues the rest
SYNC_LIMIT = 30


@frappe.whitelist()
def get_employees(values: dict | str, advanced_filters: list | str | None = None) -> list:
	"""Active employees with no submitted assignment on the From Date, with their grade's base pay."""
	tool = get_tool(values)
	return tool.get_employees(get_advanced_filters(advanced_filters))


@frappe.whitelist(methods=["POST"])
def bulk_assign(values: dict | str, employees: list | str) -> dict:
	"""Runs the tool's bulk assignment. The Desk form gets the result through a realtime event,
	so for a run in this request the created assignments are read back."""
	tool = get_tool(values)
	employees = frappe.parse_json(employees)
	started = now_datetime()
	tool.bulk_assign_structure(employees)
	if len(employees) > SYNC_LIMIT:
		return {"queued": True}

	names = [d["employee"] for d in employees]
	created = frappe.get_all(
		"Salary Structure Assignment",
		filters={
			"employee": ("in", names),
			"salary_structure": tool.salary_structure,
			"from_date": tool.from_date,
			"docstatus": 1,
			"creation": (">=", started),
		},
		fields=["name", "employee", "employee_name"],
	)
	done = {d.employee for d in created}
	return {"queued": False, "created": created, "failed": [e for e in names if e not in done]}


def get_tool(values: dict | str):
	"""An unsaved tool document with the form values, as the Desk form sends it."""
	if not frappe.has_permission(DOCTYPE, "write"):
		frappe.throw(_("Not permitted to use {0}").format(_(DOCTYPE)), frappe.PermissionError)
	values = frappe.parse_json(values)
	fieldnames = set(frappe.get_meta(DOCTYPE).get_valid_columns())
	return frappe.get_doc({"doctype": DOCTYPE, **{k: v for k, v in values.items() if k in fieldnames}})
