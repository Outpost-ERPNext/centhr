"""Records the PMS tests create in their own transaction, which is rolled back when they finish."""

import frappe

from centhr.pms import kpi
from centhr.pms.period import KpiMonth

UOM = "_Test PMS %"
KPI_ITEMS = [
	{"kpi": "Sales closed", "uom": UOM, "target": 100, "weight": "60", "polarity": "Positive"},
	{"kpi": "Complaints", "uom": UOM, "target": 5, "weight": "40", "polarity": "Negative"},
]


def make_uom() -> None:
	if not frappe.db.exists("KPI UOM", UOM):
		frappe.get_doc({"doctype": "KPI UOM", "name1": UOM}).insert()


def submit_kpi_result(employee: str, fiscal_year: str, month: str, achieved: tuple[float, float]):
	"""A submitted KPI Template and the submitted KPI Result made from it."""
	template = kpi.make_template(KpiMonth(fiscal_year, month), employee, KPI_ITEMS).insert()
	template.submit()
	result = frappe.get_doc("KPI Result", {"kpi_template": template.name})
	for row, value in zip(result.items, achieved, strict=True):
		row.achieved = value
	result.submit()
	return result


def get_fiscal_year_2031() -> str:
	"""The calendar year 2031: far enough ahead to have no KPI records. Fiscal years cannot overlap,
	so a site that has this year already uses its own."""
	year = {"year_start_date": "2031-01-01", "year_end_date": "2031-12-31"}
	existing = frappe.db.get_value("Fiscal Year", year, "name")
	return (
		existing or frappe.get_doc({"doctype": "Fiscal Year", "year": "_Test PMS 2031", **year}).insert().name
	)


def make_settings(company: str) -> None:
	settings = (
		frappe.get_doc("PMS Settings", company)
		if frappe.db.exists("PMS Settings", company)
		else frappe.get_doc({"doctype": "PMS Settings", "company": company})
	)
	settings.update({"overall_kpi_weight": 70, "overall__360_weight": 30, "kpi_freeze_day": 0})
	settings.set("kpi_score", [{"score": "0-50", "remark": "Below"}, {"score": "51-100", "remark": "Met"}])
	settings.save()


def make_department(company: str, name: str) -> str:
	parent = frappe.db.get_value(
		"Department", {"is_group": 1, "parent_department": ["is", "not set"]}, "name"
	)
	return (
		frappe.get_doc(
			{
				"doctype": "Department",
				"department_name": name,
				"company": company,
				"parent_department": parent,
			}
		)
		.insert()
		.name
	)


def make_user(name: str, roles: list[str]) -> str:
	user = frappe.get_doc(
		{
			"doctype": "User",
			"email": f"{name.lower()}@pms-test.example",
			"first_name": name,
			"send_welcome_email": 0,
			"roles": [{"role": role} for role in roles],
		}
	).insert()
	return user.name


def make_employee(
	company: str,
	first_name: str,
	department: str | None,
	reports_to: str | None = None,
	roles=("PMS User",),
	grade: str | None = None,
):
	employee = frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": first_name,
			"last_name": "PMS Test",
			"company": company,
			"department": department,
			"grade": grade,
			"gender": frappe.db.get_value("Gender", {}, "name"),
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"status": "Active",
			"reports_to": reports_to,
			# Frappe throttles user creation, so only employees who log in during a test get a user
			"user_id": make_user(f"pms-{first_name}", list(roles)) if roles else None,
		}
	)
	# The payroll fields CentHR makes mandatory on Employee do not matter here
	employee.flags.ignore_mandatory = True
	return employee.insert()
