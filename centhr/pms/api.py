"""Whitelisted methods of the PMS pages in the CentHR UI."""

import frappe
from frappe import _

from centhr.pms import kpi
from centhr.pms.period import KpiMonth

TEMPLATE_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"company",
	"department",
	"designation",
	"reviewer",
	"docstatus",
]
RESULT_FIELDS = ["name", "employee", "kpi_template", "docstatus", "overall_score", "remark"]


@frappe.whitelist(methods=["POST"])
def create_kpi_templates(
	fiscal_year: str, month: str, department: str, items: list[dict] | str, designation: str | None = None
) -> dict:
	"""Give every active employee of a department (or of one designation in it) the same KPIs for a month."""
	frappe.has_permission(kpi.TEMPLATE, "create", throw=True)
	frappe.has_permission("Department", "read", doc=department, throw=True)

	items = frappe.parse_json(items) if isinstance(items, str) else items
	if not items:
		frappe.throw(_("Add at least one KPI."))
	return kpi.DepartmentTemplates(KpiMonth(fiscal_year, month), department, items, designation).create()


@frappe.whitelist(methods=["POST"])
def copy_kpi_templates(company: str) -> dict:
	"""Prepare this month's draft KPI Templates of a company from last month's, as the scheduler does on the 27th."""
	frappe.has_permission(kpi.TEMPLATE, "create", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)

	copy = kpi.MonthlyCopy(company)
	return {"created": copy.run(), "month": copy.month.label, "source": copy.source.label}


@frappe.whitelist()
def get_kpi_dashboard(
	fiscal_year: str, month: str, company: str | None = None, department: str | None = None
) -> list[dict]:
	"""The month's KPI Templates the user may see, each with its KPI Result. For a line manager these
	are their direct reports and their own."""
	filters = {"fiscal_year": fiscal_year, "month": month, "docstatus": ["!=", 2]}
	if company:
		filters["company"] = company
	if department:
		filters["department"] = department

	templates = frappe.get_list(
		kpi.TEMPLATE,
		filters=filters,
		fields=TEMPLATE_FIELDS,
		order_by="employee_name asc",
		limit=0,
	)
	results = {
		result.kpi_template: result
		for result in frappe.get_list(
			kpi.RESULT,
			filters={**filters, "kpi_template": ["in", [t.name for t in templates]]},
			fields=RESULT_FIELDS,
			limit=0,
		)
	}
	return [{**template, "result": results.get(template.name)} for template in templates]
