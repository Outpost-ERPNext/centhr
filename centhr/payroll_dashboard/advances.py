"""Advances & Deductions tab: unrecovered employee advances and this cycle's deductions."""

import frappe
from frappe import _
from hrms.hr.doctype.employee_advance.employee_advance import create_return_through_additional_salary

from centhr.payroll_dashboard.scope import Scope


def get_advances(scope: Scope) -> dict:
	return {"advances": get_pending_advances(scope), "deductions": get_cycle_deductions(scope)}


def get_pending_advances(scope: Scope) -> list:
	"""Paid advances the employee has not settled by expense claim or return."""
	if not frappe.has_permission("Employee Advance", "read"):
		return []
	rows = frappe.get_list(
		"Employee Advance",
		filters={**scope.company_filter, "docstatus": 1, "pending_amount": [">", 0]},
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"posting_date",
			"purpose",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"pending_amount",
			"repay_unclaimed_amount_from_salary",
			"currency",
			"status",
		],
		order_by="posting_date asc",
		limit_page_length=0,
	)
	recovering = set(
		frappe.get_all(
			"Additional Salary",
			filters={"ref_doctype": "Employee Advance", "ref_docname": ["in", [r.name for r in rows] or [""]], "docstatus": ["<", 2]},
			pluck="ref_docname",
		)
	)
	for row in rows:
		row.overdue = row.posting_date and frappe.utils.getdate(row.posting_date) <= scope.to_date
		row.recovery_scheduled = row.name in recovering
	return rows


def get_cycle_deductions(scope: Scope) -> list:
	if not frappe.has_permission("Additional Salary", "read"):
		return []
	return frappe.get_list(
		"Additional Salary",
		filters={
			**scope.company_filter,
			"docstatus": 1,
			"type": "Deduction",
			"payroll_date": ["between", [scope.from_date, scope.to_date]],
		},
		fields=["name", "employee", "employee_name", "salary_component", "amount", "currency", "ref_doctype", "ref_docname", "payroll_date"],
		order_by="employee asc",
		limit_page_length=0,
	)


def recover_advance(advance: str, salary_component: str, payroll_date: str) -> str:
	"""Deducts the advance's unrecovered amount from the employee's salary, as the Employee Advance form does."""
	doc = frappe.get_doc("Employee Advance", advance)
	doc.check_permission("read")
	if not doc.repay_unclaimed_amount_from_salary:
		frappe.throw(_("Tick Repay Unclaimed Amount from Salary on {0} to recover it through payroll.").format(advance))
	additional = create_return_through_additional_salary(doc)
	additional.update({"salary_component": salary_component, "payroll_date": payroll_date, "amount": doc.pending_amount})
	additional.insert()
	additional.submit()
	return additional.name
