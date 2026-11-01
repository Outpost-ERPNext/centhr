import frappe
from frappe import _
from frappe.utils import getdate
from frappe.utils.xlsxutils import build_xlsx_response

# Label and row key of each column in the Excel export
EXPORT_COLUMNS = [
	(_("Employee ID"), "name"),
	(_("Employee Name"), "employee_name"),
	(_("Company"), "company"),
	(_("Department"), "department"),
	(_("Designation"), "designation"),
	(_("Status"), "status"),
	(_("Salary Structure"), "salary_structure"),
	(_("Base Salary"), "base"),
	(_("Effective Since"), "effective_from"),
	(_("Payroll Status"), "slip_status"),
	(_("Gross Pay"), "gross_pay"),
	(_("Deductions"), "total_deduction"),
	(_("Net Pay"), "net_pay"),
]


@frappe.whitelist()
def get_salary_overview(from_date: str, to_date: str, company: str | None = None) -> list[dict]:
	"""One row per employee in the payroll period, with their salary structure and salary slip.
	Without a company, employees of every company the user can see."""
	return SalaryOverview(company, from_date, to_date).get_rows()


@frappe.whitelist(methods=["POST"])
def export_salary_overview(
	from_date: str, to_date: str, company: str | None = None, employees: list[str] | str | None = None
):
	"""The overview as an Excel file; `employees` keeps the rows and order the page shows."""
	rows = SalaryOverview(company, from_date, to_date).get_rows()
	# A form POST sends the list as JSON
	employees = frappe.parse_json(employees) if isinstance(employees, str) else employees
	if employees is not None:
		by_name = {row["name"]: row for row in rows}
		rows = [by_name[name] for name in employees if name in by_name]

	data = [[label for label, _key in EXPORT_COLUMNS]]
	data += [[row.get(key) for _label, key in EXPORT_COLUMNS] for row in rows]
	build_xlsx_response(data, f"Payroll {company or 'All Companies'} {from_date} to {to_date}")


class SalaryOverview:
	"""Active employees plus those who left in the period, as they still get a final salary slip.
	Every query goes through get_list, so the user's permissions apply."""

	def __init__(self, company: str | None, from_date: str, to_date: str):
		# Employees and their records are filtered by company only when one is chosen
		self.company_filter = {"company": company} if company else {}
		self.from_date = getdate(from_date)
		self.to_date = getdate(to_date)

	def get_rows(self) -> list[dict]:
		employees = self.get_employees()
		names = [e.name for e in employees]
		assignments = self.get_assignments(names)
		slips = self.get_slips(names)
		inactive = self.get_inactive_structures({a.salary_structure for a in assignments.values()})

		return [self.make_row(e, assignments.get(e.name), slips.get(e.name), inactive) for e in employees]

	def make_row(self, employee, assignment, slip, inactive_structures: set[str]) -> dict:
		structure = assignment.salary_structure if assignment else None
		return {
			**employee,
			"assignment": assignment.name if assignment else None,
			"salary_structure": structure,
			"structure_inactive": structure in inactive_structures,
			"base": assignment.base if assignment else None,
			"currency": assignment.currency if assignment else None,
			"effective_from": assignment.from_date if assignment else None,
			"salary_slip": slip.name if slip else None,
			"slip_status": slip.status if slip else None,
			"gross_pay": slip.gross_pay if slip else None,
			"total_deduction": slip.total_deduction if slip else None,
			"net_pay": slip.net_pay if slip else None,
		}

	def get_employees(self) -> list:
		return frappe.get_list(
			"Employee",
			filters=self.company_filter,
			or_filters=[
				["status", "=", "Active"],
				["relieving_date", "between", [self.from_date, self.to_date]],
			],
			fields=[
				"name",
				"employee_name",
				"company",
				"department",
				"designation",
				"status",
				"date_of_joining",
				"relieving_date",
				"salary_mode",
				"bank_ac_no",
			],
			order_by="name asc",
			limit_page_length=0,
		)

	def get_assignments(self, employees: list[str]) -> dict:
		"""The latest submitted assignment that applies by the end of the period."""
		return self.get_by_employee(
			"Salary Structure Assignment",
			employees,
			filters={**self.company_filter, "docstatus": 1, "from_date": ["<=", self.to_date]},
			fields=["name", "salary_structure", "base", "currency", "from_date"],
			order_by="from_date asc",
		)

	def get_slips(self, employees: list[str]) -> dict:
		# The overview still works for users who cannot read salary slips
		if not frappe.has_permission("Salary Slip", "read"):
			return {}
		return self.get_by_employee(
			"Salary Slip",
			employees,
			filters={
				**self.company_filter,
				"docstatus": ["!=", 2],
				"start_date": ["<=", self.to_date],
				"end_date": [">=", self.from_date],
			},
			fields=["name", "status", "gross_pay", "total_deduction", "net_pay"],
			order_by="start_date asc",
		)

	def get_inactive_structures(self, structures: set[str]) -> set[str]:
		if not structures:
			return set()
		return set(
			frappe.get_all(
				"Salary Structure",
				filters={"name": ["in", list(structures)], "is_active": "No"},
				pluck="name",
			)
		)

	@staticmethod
	def get_by_employee(doctype: str, employees: list[str], filters: dict, fields: list[str], order_by: str) -> dict:
		"""Rows keyed by employee; sorted ascending, so the latest row of each employee wins."""
		if not employees:
			return {}
		rows = frappe.get_list(
			doctype,
			filters={**filters, "employee": ["in", employees]},
			fields=["employee", *fields],
			order_by=order_by,
			limit_page_length=0,
		)
		return {row.employee: row for row in rows}
