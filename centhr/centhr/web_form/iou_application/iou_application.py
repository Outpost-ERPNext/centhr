import frappe
from frappe.rate_limiter import rate_limit

from centhr.iou.advance import get_open_advance


def get_context(context):
	pass


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 10)
def get_iou_status(employee: str) -> dict:
	"""What the web form tells the employee before they apply: the bank details on file, and any IOU
	that blocks a new application (SOP: one IOU at a time). Amounts stay hidden from the open form."""
	if not frappe.db.exists("Employee", {"name": employee, "status": "Active"}):
		return {}
	bank_name, bank_ac_no = frappe.db.get_value("Employee", employee, ["bank_name", "bank_ac_no"])
	pending = frappe.db.get_value(
		"Employee Advance",
		{"employee": employee, "docstatus": 0, "workflow_state": ["!=", "Rejected"]},
		"name",
	)
	open_advance = get_open_advance(employee)
	return {
		"bank_name": bank_name,
		"bank_ac_no": bank_ac_no,
		"pending_iou": pending,
		"open_iou": open_advance.name if open_advance else None,
	}
