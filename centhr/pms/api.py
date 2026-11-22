"""Whitelisted methods of the PMS pages in the CentHR UI."""

import frappe
from frappe import _

from centhr.pms import kpi, peers, permissions, review, reviewer, score_sheet
from centhr.pms.overall import OverallScores
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
def get_latest_kpi_month() -> dict | None:
	"""The newest month that has KPI Templates; None before the first template exists."""
	month = kpi.get_latest_month()
	return {"fiscal_year": month.fiscal_year, "month": month.month} if month else None


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


@frappe.whitelist(methods=["POST"])
def run_peer_mapping(company: str) -> dict:
	"""Create and refresh the peer mappings of a company, as the scheduler does on the 1st and 16th."""
	frappe.has_permission(peers.MAPPING, "write", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	return peers.PeerMapping(company).run()


@frappe.whitelist(methods=["POST"])
def set_peer_mapping_lock(employee: str, locked: bool | int) -> bool:
	"""Lock a mapping HR has checked, or unlock it to change it."""
	mapping = frappe.get_doc(peers.MAPPING, employee)
	mapping.check_permission("write")
	mapping.set_lock(bool(int(locked)))
	return bool(mapping.locked)


# 360 review


@frappe.whitelist(methods=["POST"])
def create_questionnaires(
	company: str,
	fiscal_year: str,
	quarter: str,
	questions: list[dict] | str,
	departments: list[str] | str | None = None,
	designation: str | None = None,
	preview: bool | int = False,
) -> dict:
	"""Create PMS Form: give the questions to the eligible employees. With `preview`, only report who
	would get them and who is skipped, and why."""
	frappe.has_permission(review.QUESTIONNAIRE, "create", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	builder = review.QuestionnaireBuilder(
		company, fiscal_year, quarter, parse(questions), parse(departments), designation
	)
	return builder.run(preview=bool(int(preview)))


@frappe.whitelist()
def get_questionnaires(
	fiscal_year: str, quarter: str, company: str | None = None, department: str | None = None
) -> list[dict]:
	"""Form Dashboard: the quarter's questionnaires with their number of questions and reviews."""
	filters = {"fiscal_year": fiscal_year, "quarter": quarter}
	if company:
		filters["company"] = company
	if department:
		filters["department"] = department
	rows = frappe.get_list(
		review.QUESTIONNAIRE,
		filters=filters,
		fields=["name", "employee", "employee_name", "company", "department", "status"],
		order_by="employee_name asc",
		limit=0,
	)
	names = [row.name for row in rows]
	questions = count_by("PMS Questionnaire List", "parent", {"parent": ["in", names]})
	asked = count_by(review.ALLOCATION, "form_reference", {"form_reference": ["in", names], "docstatus": 1})
	done = count_by(
		review.ALLOCATION,
		"form_reference",
		{"form_reference": ["in", names], "docstatus": 1, "status": "Completed"},
	)
	return [
		{
			**row,
			"questions": questions.get(row.name, 0),
			"reviews_total": asked.get(row.name, 0),
			"reviews_done": done.get(row.name, 0),
		}
		for row in rows
	]


@frappe.whitelist(methods=["POST"])
def close_questionnaires(names: list[str] | str) -> dict:
	"""Close questionnaires and ask their reviewers. Returns the ones closed and the ones that failed."""
	return review.close_questionnaires(parse(names))


@frappe.whitelist(methods=["POST"])
def reopen_questionnaire(name: str) -> None:
	review.reopen_questionnaire(name)


@frappe.whitelist()
def get_review_status(
	fiscal_year: str, quarter: str, company: str | None = None, department: str | None = None
) -> list[dict]:
	"""Form Submission Status: every review asked for in the quarter and whether it is in."""
	filters = {"fiscal_year": fiscal_year, "quarter": quarter, "docstatus": 1}
	if company:
		filters["company"] = company
	if department:
		filters["department"] = department
	return frappe.get_list(
		review.ALLOCATION,
		filters=filters,
		fields=[
			"name",
			"reviewee",
			"reviewee_name",
			"reviewer",
			"reviewer_name",
			"department",
			"relationship_type",
			"status",
			"review_date",
		],
		order_by="reviewee_name asc, relationship_type asc",
		limit=0,
	)


@frappe.whitelist()
def get_my_reviews() -> list[dict]:
	"""The reviews the logged-in employee is asked to give."""
	employee = permissions.get_employee(frappe.session.user)
	return reviewer.get_my_reviews(employee) if employee else []


@frappe.whitelist()
def get_review_form(allocation: str) -> dict:
	return reviewer.get_review_form(allocation, permissions.get_employee(frappe.session.user))


@frappe.whitelist(methods=["POST"])
def submit_review(allocation: str, answers: list[dict] | str, remarks: str | None = None) -> str:
	"""Submit the logged-in employee's review. Only the reviewer named on the allocation can."""
	employee = permissions.get_employee(frappe.session.user)
	return reviewer.submit_review(allocation, employee, parse(answers), remarks)


# Results


@frappe.whitelist()
def get_overall_scores(
	fiscal_year: str,
	quarter: str | None = None,
	month: str | None = None,
	company: str | None = None,
	department: str | None = None,
) -> list[dict]:
	"""Overall Score Dashboard: KPI score, 360 score and overall score of a month or a quarter."""
	if not quarter and not month:
		frappe.throw(_("Choose a month or a quarter."))
	return OverallScores(fiscal_year, quarter, month, company, department).get_rows()


@frappe.whitelist(methods=["POST"])
def generate_score_sheets(company: str, fiscal_year: str, quarter: str) -> dict:
	"""Draft Score Sheets for the employees of the company who have an overall score for the quarter."""
	frappe.has_permission(score_sheet.SCORE_SHEET, "create", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	return score_sheet.generate(company, fiscal_year, quarter)


@frappe.whitelist(methods=["POST"])
def decide_score_sheets(names: list[str] | str, decision: str) -> int:
	"""Approve (submit) or reject Score Sheets."""
	if decision not in ("approve", "reject"):
		frappe.throw(_("Unknown decision {0}.").format(decision))
	names = parse(names)
	for name in names:
		sheet = frappe.get_doc(score_sheet.SCORE_SHEET, name)
		if decision == "approve":
			sheet.submit()
		else:
			sheet.check_permission("write")
			sheet.reject()
	return len(names)


def parse(value):
	return frappe.parse_json(value) if isinstance(value, str) else value


def count_by(doctype: str, field: str, filters: dict) -> dict[str, int]:
	rows = frappe.get_all(
		doctype, filters=filters, fields=[field, {"COUNT": "*", "as": "count"}], group_by=field
	)
	return {row[field]: row["count"] for row in rows}
