import frappe
from frappe.rate_limiter import rate_limit

from centhr.iou.advance import get_open_advance


def get_context(context):
	pass


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=60, seconds=60 * 10)
def get_open_iou(employee: str) -> dict:
	"""The IOU the claim settles, with its outstanding amount and due date (SOP: linked IOU fills in)."""
	if not frappe.db.exists("Employee", {"name": employee, "status": "Active"}):
		return {}
	advance = get_open_advance(employee)
	if not advance:
		return {}
	return {
		"name": advance.name,
		"purpose": advance.purpose,
		"currency": advance.currency,
		"outstanding_amount": advance.outstanding_amount,
		"due_date": advance.due_date,
	}
