"""The overall score of a month or a quarter: the KPI score and the 360 score together."""

import frappe
from frappe.utils import flt

from centhr.pms import permissions
from centhr.pms.period import QUARTERS, quarter_of
from centhr.pms.scoring import find_band_row, overall_score, review_score

EMPLOYEE_FIELDS = ["name", "employee_name", "company", "department", "designation"]


class OverallScores:
	"""One row per active employee the user may see. For a month, the KPI score is that month's and
	the 360 score is its quarter's; for a quarter, the KPI score is the average of its months.
	Only submitted KPI Results and submitted reviews count."""

	def __init__(
		self,
		fiscal_year: str,
		quarter: str | None = None,
		month: str | None = None,
		company: str | None = None,
		department: str | None = None,
	):
		self.fiscal_year = fiscal_year
		self.months = [month] if month else list(QUARTERS[quarter])
		self.quarter = quarter_of(month) if month else quarter
		self.company = company
		self.department = department
		self.settings = {}

	def get_rows(self) -> list[dict]:
		employees = self.get_employees()
		names = [employee.name for employee in employees]
		kpi_scores = self.get_kpi_scores(names)
		reviews = get_review_scores(names, self.fiscal_year, self.quarter)
		return [
			self.make_row(employee, kpi_scores.get(employee.name), reviews.get(employee.name))
			for employee in employees
		]

	def get_employees(self) -> list:
		filters = {"status": "Active"}
		if self.company:
			filters["company"] = self.company
		if self.department:
			filters["department"] = self.department

		user = frappe.session.user
		if permissions.is_hr(user):
			# HR sees every employee of the companies their user permissions allow
			return frappe.get_list(
				"Employee", filters=filters, fields=EMPLOYEE_FIELDS, order_by="employee_name asc", limit=0
			)
		filters["reports_to"] = permissions.get_employee(user) or "-"
		return frappe.get_all(
			"Employee", filters=filters, fields=EMPLOYEE_FIELDS, order_by="employee_name asc"
		)

	def get_kpi_scores(self, employees: list[str]) -> dict[str, float]:
		if not employees:
			return {}
		results = frappe.get_all(
			"KPI Result",
			filters={
				"employee": ["in", employees],
				"fiscal_year": self.fiscal_year,
				"month": ["in", self.months],
				"docstatus": 1,
			},
			fields=["employee", "overall_score"],
		)
		by_employee = {}
		for result in results:
			by_employee.setdefault(result.employee, []).append(flt(result.overall_score))
		return {employee: round(sum(scores) / len(scores), 2) for employee, scores in by_employee.items()}

	def make_row(self, employee, kpi_score: float | None, review: dict | None) -> dict:
		review = review or {"score": None, "done": 0, "total": 0}
		settings = self.get_settings(employee.company)
		score = overall_score(kpi_score, review["score"], settings) if settings else None
		band = find_band_row(score, settings.overall_score) if score is not None else None
		return {
			**employee,
			"employee": employee.name,
			"kpi_score": kpi_score,
			"review_score": review["score"],
			"reviews_done": review["done"],
			"reviews_total": review["total"],
			"overall_score": score,
			"overall_remark": band.remark if band else None,
		}

	def get_settings(self, company: str):
		"""None for a company that has no PMS Settings yet; its employees then have no overall score."""
		if company not in self.settings:
			exists = frappe.db.exists("PMS Settings", company)
			self.settings[company] = frappe.get_cached_doc("PMS Settings", company) if exists else None
		return self.settings[company]


def get_review_scores(employees: list[str], fiscal_year: str, quarter: str) -> dict[str, dict]:
	"""Each employee's 360 score of the quarter from the reviews received so far, with how many of
	the reviews asked for are in."""
	if not employees:
		return {}
	allocations = frappe.get_all(
		"PMS Form Allocation",
		filters={
			"reviewee": ["in", employees],
			"fiscal_year": fiscal_year,
			"quarter": quarter,
			"docstatus": 1,
		},
		fields=["name", "reviewee", "status"],
	)
	reviews = frappe.get_all(
		"PMS Question Form",
		filters={"pms_form_allocation": ["in", [a.name for a in allocations]], "docstatus": 1},
		fields=["reviewee", "relationship_type", "rating_score", "superior_weight", "peers_weight"],
	)

	scores = {}
	for allocation in allocations:
		entry = scores.setdefault(allocation.reviewee, {"score": None, "done": 0, "total": 0, "reviews": []})
		entry["total"] += 1
		entry["done"] += int(allocation.status == "Completed")
	for review in reviews:
		weight = review.peers_weight if review.relationship_type == "Peers" else review.superior_weight
		scores[review.reviewee]["reviews"].append((review.rating_score, weight))
	for entry in scores.values():
		entry["score"] = review_score(entry.pop("reviews"))
	return scores
