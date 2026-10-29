import frappe
from frappe.utils import getdate


@frappe.whitelist()
def get_salary_overview(company: str, from_date: str, to_date: str) -> list[dict]:
	"""One row per employee of the company in the payroll period, with their salary structure and salary slip."""
	return SalaryOverview(company, from_date, to_date).get_rows()


class SalaryOverview:
	"""Active employees plus those who left in the period, as they still get a final salary slip.
	Every query goes through get_list, so the user's permissions apply."""

	def __init__(self, company: str, from_date: str, to_date: str):
		self.company = company
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
			filters={"company": self.company},
			or_filters=[
				["status", "=", "Active"],
				["relieving_date", "between", [self.from_date, self.to_date]],
			],
			fields=["name", "employee_name", "department", "designation", "status", "date_of_joining", "relieving_date"],
			order_by="name asc",
			limit_page_length=0,
		)

	def get_assignments(self, employees: list[str]) -> dict:
		"""The latest submitted assignment that applies by the end of the period."""
		return self.get_by_employee(
			"Salary Structure Assignment",
			employees,
			filters={"company": self.company, "docstatus": 1, "from_date": ["<=", self.to_date]},
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
				"company": self.company,
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
