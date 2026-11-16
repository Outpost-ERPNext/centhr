"""Score Sheets: what each employee's overall score of a quarter leads to."""

import frappe

from centhr.pms.overall import OverallScores

SCORE_SHEET = "PMS Score Sheet"


def generate(company: str, fiscal_year: str, quarter: str) -> dict:
	"""A draft Score Sheet for every employee of the company who has an overall score for the quarter
	and no sheet yet. Employees still waiting for their KPI or 360 score are counted as not ready."""
	rows = OverallScores(fiscal_year, quarter=quarter, company=company).get_rows()
	have = set(
		frappe.get_all(
			SCORE_SHEET,
			filters={
				"company": company,
				"fiscal_year": fiscal_year,
				"quarter": quarter,
				"docstatus": ["!=", 2],
			},
			pluck="employee",
		)
	)
	ready = [row for row in rows if row["overall_score"] is not None]
	created = [create(row, fiscal_year, quarter) for row in ready if row["employee"] not in have]
	return {"created": created, "existing": len(ready) - len(created), "not_ready": len(rows) - len(ready)}


def create(row: dict, fiscal_year: str, quarter: str) -> str:
	questionnaire = frappe.db.get_value(
		"PMS Questionnaire",
		{"employee": row["employee"], "fiscal_year": fiscal_year, "quarter": quarter},
		"name",
	)
	return (
		frappe.get_doc(
			{
				"doctype": SCORE_SHEET,
				"employee": row["employee"],
				"department": row["department"],
				"fiscal_year": fiscal_year,
				"quarter": quarter,
				"pms_questionnaire": questionnaire,
				"kpi_score": row["kpi_score"],
				"review_score": row["review_score"],
				"calculated_score": row["overall_score"],
			}
		)
		.insert()
		.name
	)
