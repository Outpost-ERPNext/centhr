import frappe

from centhr.centhr.doctype.centhr_api_logger.readable_error import get_readable_error


def execute():
	logs = frappe.get_all(
		"CentHR API Logger",
		filters={"error": ("is", "set"), "error_details": ("is", "not set")},
		fields=["name", "doctypes", "reference_name", "company", "error", "http_status", "endpoint", "api_response"],
	)

	for log in logs:
		readable = get_readable_error(log)
		if readable and readable != log.error:
			frappe.db.set_value(
				"CentHR API Logger",
				log.name,
				{"error": readable, "error_details": log.error},
				update_modified=False,
			)
