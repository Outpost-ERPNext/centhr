import frappe
from frappe import _

# The buttons of the Desk Holiday List form; they change the holidays table without saving
TABLE_METHODS = ("get_weekly_off_dates", "get_local_holidays", "clear_table")


@frappe.whitelist(methods=["POST"])
def update_holidays(doc: dict | str, method: str) -> dict:
	"""Runs a Holiday List table button on the unsaved form values and returns the new table.
	The user saves the list afterwards, as in Desk."""
	if method not in TABLE_METHODS:
		frappe.throw(_("{0} is not a Holiday List action").format(method))

	doc = frappe.get_doc(frappe.parse_json(doc))
	if doc.doctype != "Holiday List":
		frappe.throw(_("Only Holiday Lists can be updated here"))
	doc.check_permission("create" if doc.is_new() else "write")

	doc.run_method(method)
	return {
		"holidays": [row.as_dict(convert_dates_to_str=True) for row in doc.holidays],
		"total_holidays": doc.total_holidays,
	}


@frappe.whitelist()
def get_supported_countries() -> dict:
	"""Countries and their subdivisions for the Country and Subdivision pickers, as in the Desk form."""
	if not frappe.has_permission("Holiday List", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.new_doc("Holiday List").get_supported_countries()
