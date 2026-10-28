import frappe


@frappe.whitelist(methods=["POST"])
def fill_payroll_employees(payroll_entry: str) -> list[dict] | None:
	"""Fills a draft Payroll Entry's employees and saves it, as the "Get Employees" button does in Desk.
	Returns the employees with unmarked attendance when the entry validates attendance."""
	doc = frappe.get_doc("Payroll Entry", payroll_entry)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(frappe._("Employees can only be fetched for a draft Payroll Entry."))
	unmarked = doc.fill_employee_details()
	doc.save()
	return unmarked
