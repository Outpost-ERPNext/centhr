import frappe

from centhr.api.post.employee import TARGET_REQUIRED_FIELDS, get_targets


@frappe.whitelist()
def get_entity_sync_requirements(company: str) -> dict:
	"""Fields a new Employee needs so the sync to the company's entity site succeeds.
	Returns no credentials, only whether the company syncs and which fields it requires."""
	if not (frappe.has_permission("Employee", "create") or frappe.has_permission("Employee", "write")):
		frappe.throw(frappe._("Not permitted"), frappe.PermissionError)

	syncs = bool(company) and bool(get_targets(company))
	return {"syncs": syncs, "required_fields": list(TARGET_REQUIRED_FIELDS) if syncs else []}


@frappe.whitelist()
def get_entity_sync_status(employee: str) -> list[dict]:
	"""Latest Employee sync result for each entity site of the employee's company."""
	doc = frappe.get_doc("Employee", employee)
	doc.check_permission("read")

	if not get_targets(doc.company):
		return []

	logs = frappe.get_all(
		"CentHR API Logger",
		filters={"doctypes": "Employee", "reference_name": employee},
		fields=["status", "error", "company", "creation", "request_method"],
		order_by="creation desc",
		limit=1,
	)
	if not logs:
		return [{"company": doc.company, "status": "Pending", "error": None, "creation": None}]
	return logs
