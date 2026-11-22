"""The monthly KPI cycle: one KPI Template per employee, and the KPI Result made from it."""

from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, getdate, today

from centhr.centhr.doctype.pms_settings.pms_settings import get_settings
from centhr.pms.period import MONTHS, KpiMonth

TEMPLATE = "KPI Template"
RESULT = "KPI Result"
# Day of the month the scheduler prepares the month's templates from last month's
COPY_DAY = 27
ITEM_FIELDS = ("kpi", "uom", "target", "weight", "polarity")


def get_latest_month() -> KpiMonth | None:
	"""The newest month, up to today, that has KPI Templates the user may see. The KPI pages open on
	it, so a site whose KPIs stop at an earlier month, such as one that was migrated, shows them."""
	periods = frappe.get_list(
		TEMPLATE,
		filters={"docstatus": ["!=", 2]},
		fields=["fiscal_year", "month"],
		group_by="fiscal_year, month",
		limit=0,
	)
	months = [KpiMonth(period.fiscal_year, period.month) for period in periods if period.month in MONTHS]
	started = [month for month in months if month.starts_by(getdate(today()))]
	# Templates of months to come only: the first of them is the nearest
	return (
		max(started, key=lambda m: m.start) if started else min(months, key=lambda m: m.start, default=None)
	)


class DepartmentTemplates:
	"""Gives every active employee of a department, or of one designation in it, the same KPIs for a
	month. Employees who already have a template for the month keep it."""

	def __init__(self, month: KpiMonth, department: str, items: list[dict], designation: str | None = None):
		self.month = month
		self.department = department
		self.designation = designation
		self.items = items

	def create(self) -> dict:
		employees = self.get_employees()
		if not employees:
			frappe.throw(
				_("{0} has no active employees to create KPI Templates for.").format(self.department)
			)

		have = get_employees_with_template(self.month, employees)
		created = [self.create_for(employee) for employee in employees if employee not in have]
		return {"created": created, "skipped": len(have)}

	def get_employees(self) -> list[str]:
		filters = {"department": self.department, "status": "Active"}
		if self.designation:
			filters["designation"] = self.designation
		return frappe.get_all("Employee", filters=filters, pluck="name", order_by="employee_name asc")

	def create_for(self, employee: str) -> str:
		return make_template(self.month, employee, self.items).insert().name


class MonthlyCopy:
	"""Prepares a month's KPI Templates of one company from the submitted templates of the month
	before, as drafts for HR to review. Employees who left, or who have a template already, are skipped."""

	def __init__(self, company: str, day: date | str | None = None):
		self.company = company
		self.month = KpiMonth.of(day or today(), company)
		self.source = KpiMonth.of(add_months(self.month.start, -1), company)

	def run(self) -> list[str]:
		templates = self.get_source_templates()
		active = set(
			frappe.get_all(
				"Employee",
				filters={"name": ["in", [t.employee for t in templates]], "status": "Active"},
				pluck="name",
			)
		)
		have = get_employees_with_template(self.month, list(active))
		return [self.copy(t.name) for t in templates if t.employee in active and t.employee not in have]

	def get_source_templates(self) -> list:
		return frappe.get_all(
			TEMPLATE,
			filters={
				"company": self.company,
				"fiscal_year": self.source.fiscal_year,
				"month": self.source.month,
				"docstatus": 1,
			},
			fields=["name", "employee"],
		)

	def copy(self, template: str) -> str:
		source = frappe.get_doc(TEMPLATE, template)
		items = [{field: row.get(field) for field in (*ITEM_FIELDS, "notes")} for row in source.items]
		return make_template(self.month, source.employee, items).insert(ignore_permissions=True).name


def copy_templates_to_current_month() -> None:
	"""Scheduled daily; works on the 27th, for every company that has PMS Settings."""
	if getdate(today()).day != COPY_DAY:
		return
	for company in frappe.get_all("PMS Settings", pluck="company"):
		try:
			MonthlyCopy(company).run()
			frappe.db.commit()
		except Exception:
			# One company without a fiscal year must not stop the others
			frappe.db.rollback()
			frappe.log_error(title=f"KPI Templates of {company} were not copied to the new month")


def make_template(month: KpiMonth, employee: str, items: list[dict]):
	return frappe.get_doc(
		{
			"doctype": TEMPLATE,
			"fiscal_year": month.fiscal_year,
			"month": month.month,
			"employee": employee,
			"items": [{field: item.get(field) for field in (*ITEM_FIELDS, "notes")} for item in items],
		}
	)


def get_employees_with_template(month: KpiMonth, employees: list[str]) -> set[str]:
	if not employees:
		return set()
	return set(
		frappe.get_all(
			TEMPLATE,
			filters={
				"fiscal_year": month.fiscal_year,
				"month": month.month,
				"employee": ["in", employees],
				"docstatus": ["!=", 2],
			},
			pluck="employee",
		)
	)


# Shared by the KPI Template and KPI Result controllers


def make_name(prefix: str, doc) -> str:
	"""KPI-T|03-2026|S-EMP-00012. A cancelled record keeps its name, so a later one gets a counter."""
	base = f"{prefix}|{MONTHS.index(doc.month) + 1:02d}-{doc.fiscal_year}|{doc.employee}"
	name, count = base, 0
	while frappe.db.exists(doc.doctype, name):
		count += 1
		name = f"{base}|{count}"
	return name


def set_employee_details(doc) -> None:
	"""Company, department, designation and line manager as they are today. Records migrated from
	the CentHR site keep the department and designation the employee had at the time."""
	employee = frappe.db.get_value(
		"Employee", doc.employee, ["company", "department", "designation", "reports_to"], as_dict=True
	)
	doc.company = employee.company
	keep = bool(frappe.flags.centhr_migration)

	for field in ("department", "designation"):
		if not (keep and doc.get(field)):
			doc.set(field, employee.get(field))
	if doc.meta.has_field("reviewer") and not (keep and doc.reviewer):
		doc.reviewer = employee.reports_to

	if not doc.department and not keep:
		frappe.throw(
			_(
				"Set the Department of employee {0} first. KPIs and reviews are organised by department."
			).format(frappe.bold(doc.employee))
		)


def validate_one_per_month(doc) -> None:
	existing = frappe.db.get_value(
		doc.doctype,
		{
			"employee": doc.employee,
			"fiscal_year": doc.fiscal_year,
			"month": doc.month,
			"docstatus": ["!=", 2],
			"name": ["!=", doc.name],
		},
		"name",
	)
	if existing:
		frappe.throw(
			_("{0} already has a {1} for {2} {3}: {4}").format(
				doc.employee_name or doc.employee, _(doc.doctype), doc.month, doc.fiscal_year, existing
			),
			title=_("Already Exists"),
		)


def check_not_frozen(doc) -> None:
	"""A month's templates are final after the company's KPI Freeze Day of the following month."""
	if frappe.flags.centhr_migration or "System Manager" in frappe.get_roles():
		return
	freeze_day = get_settings(doc.company).kpi_freeze_day
	if not freeze_day:
		return

	month = KpiMonth(doc.fiscal_year, doc.month)
	freeze_date = month.freeze_date(freeze_day)
	if getdate(today()) > freeze_date:
		frappe.throw(
			_("KPI Templates for {0} are frozen since {1}. Ask a System Manager to change this one.").format(
				month.label, frappe.format(freeze_date, "Date")
			),
			title=_("Frozen"),
		)
