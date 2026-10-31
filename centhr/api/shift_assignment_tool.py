import frappe
from frappe import _
from frappe.utils import now_datetime

# The HRMS tool runs up to this many Shift Assignments in the request and queues the rest
SYNC_LIMIT = 30

# The conditions the Desk advanced filter group offers for Employee fields
FILTER_CONDITIONS = ("=", "!=", "like", "not like", "in", "not in", "is", ">", "<", ">=", "<=")


@frappe.whitelist()
def get_defaults() -> dict:
	"""The values a new tool form starts with that the meta does not hold."""
	check_permission()
	return {"company": frappe.defaults.get_user_default("Company")}


@frappe.whitelist()
def get_employees(values: dict | str, advanced_filters: list | str | None = None) -> list:
	"""Employees to assign, or the open Shift Requests, for the form values."""
	tool = get_tool(values)
	return tool.get_employees(get_advanced_filters(advanced_filters))


@frappe.whitelist(methods=["POST"])
def bulk_assign(values: dict | str, employees: list | str) -> dict:
	"""Runs the tool's bulk assignment. The Desk form gets the result through a realtime event,
	so for a run in this request the created Shift Assignments are read back."""
	tool = get_tool(values)
	employees = frappe.parse_json(employees)
	started = now_datetime()
	tool.bulk_assign(employees)
	if tool.action != "Assign Shift" or len(employees) > SYNC_LIMIT:
		return {"queued": True}

	created = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": ("in", employees),
			"shift_type": tool.shift_type,
			"start_date": tool.start_date,
			"docstatus": 1,
			"creation": (">=", started),
		},
		fields=["name", "employee", "employee_name"],
	)
	done = {d.employee for d in created}
	return {"queued": False, "created": created, "failed": [e for e in employees if e not in done]}


@frappe.whitelist(methods=["POST"])
def process_shift_requests(values: dict | str, shift_requests: list | str, status: str) -> dict:
	"""Approves or rejects Shift Requests through the tool, then reads back which ones were processed."""
	tool = get_tool(values)
	shift_requests = frappe.parse_json(shift_requests)
	tool.bulk_process_shift_requests(shift_requests, status)
	if len(shift_requests) > SYNC_LIMIT:
		return {"queued": True}

	names = [d["shift_request"] for d in shift_requests]
	processed = frappe.get_all(
		"Shift Request",
		filters={"name": ("in", names), "docstatus": 1, "status": status},
		fields=["name", "employee", "employee_name"],
	)
	done = {d.name for d in processed}
	# Desk lists the employees of the requests that failed
	failed = [d["employee"] for d in shift_requests if d["shift_request"] not in done]
	return {"queued": False, "created": processed, "failed": failed}


def get_advanced_filters(advanced_filters: list | str | None) -> list:
	"""The `[fieldname, condition, value]` filters of the Employee filter group, checked against the Employee meta."""
	filters = frappe.parse_json(advanced_filters) if advanced_filters else []
	fieldnames = set(frappe.get_meta("Employee").get_valid_columns())
	for f in filters:
		valid = isinstance(f, list) and len(f) == 3 and f[0] in fieldnames and f[1] in FILTER_CONDITIONS
		if not valid:
			frappe.throw(_("Invalid Employee filter: {0}").format(frappe.as_json(f)))
	return filters


def get_tool(values: dict | str):
	"""An unsaved Shift Assignment Tool with the form values, as the Desk form sends it."""
	check_permission()
	values = frappe.parse_json(values)
	fieldnames = set(frappe.get_meta("Shift Assignment Tool").get_valid_columns())
	return frappe.get_doc(
		{"doctype": "Shift Assignment Tool", **{k: v for k, v in values.items() if k in fieldnames}}
	)


def check_permission():
	if not frappe.has_permission("Shift Assignment Tool", "write"):
		frappe.throw(_("Not permitted to use the Shift Assignment Tool"), frappe.PermissionError)
