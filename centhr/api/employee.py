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


QUICK_VIEW_FIELDS = [
	"name",
	"employee_name",
	"image",
	"status",
	"company",
	"department",
	"designation",
	"grade",
	"branch",
	"employment_type",
	"date_of_joining",
	"relieving_date",
	"reports_to",
	"custom_no_line_manager",
	"company_email",
	"personal_email",
	"cell_number",
	"salary_mode",
	"bank_name",
	"bank_ac_no",
]


@frappe.whitelist()
def get_quick_view(employee: str, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""An employee at a glance: who they are, their salary structure, and their salary slip of the pay
	cycle (the latest slip when no cycle is given). Salary parts are left out for users who cannot read them."""
	doc = frappe.get_doc("Employee", employee)
	doc.check_permission("read")
	return {
		**{field: doc.get(field) for field in QUICK_VIEW_FIELDS},
		"reports_to_name": frappe.db.get_value("Employee", doc.reports_to, "employee_name") if doc.reports_to else None,
		"assignment": get_latest("Salary Structure Assignment", employee, ["name", "salary_structure", "base", "currency", "from_date"], "from_date"),
		"salary_slip": get_latest(
			"Salary Slip",
			employee,
			["name", "status", "start_date", "end_date", "gross_pay", "total_deduction", "net_pay", "currency"],
			"start_date",
			{"start_date": ["<=", to_date], "end_date": [">=", from_date]} if from_date and to_date else {},
			{"docstatus": ["!=", 2]},
		),
	}


def get_latest(doctype: str, employee: str, fields: list[str], date_field: str, *filters: dict) -> dict | None:
	"""The employee's newest record the user may read; submitted ones unless a filter says otherwise."""
	if not frappe.has_permission(doctype, "read"):
		return None
	merged = {"employee": employee, "docstatus": 1}
	for extra in filters:
		merged.update(extra)
	rows = frappe.get_list(doctype, filters=merged, fields=fields, order_by=f"{date_field} desc", limit=1)
	return rows[0] if rows else None
