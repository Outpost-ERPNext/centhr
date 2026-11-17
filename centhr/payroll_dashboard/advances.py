"""Advances & Deductions tab: unrecovered employee advances and this cycle's deductions."""

import frappe
from frappe import _
from hrms.hr.doctype.employee_advance.employee_advance import create_return_through_additional_salary

from centhr.iou.advance import outstanding
from centhr.payroll_dashboard.scope import Scope


def get_advances(scope: Scope) -> dict:
	return {
		"advances": get_pending_advances(scope),
		"deductions": get_cycle_deductions(scope),
		"auto_recovery": bool(
			scope.company and frappe.db.get_value("Company", scope.company, "auto_recover_advances")
		),
	}


def get_pending_advances(scope: Scope) -> list:
	"""Paid advances the employee has not settled by expense claim or return."""
	if not frappe.has_permission("Employee Advance", "read"):
		return []
	rows = frappe.get_list(
		"Employee Advance",
		filters={**scope.company_filter, "docstatus": 1, "paid_amount": [">", 0]},
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
			"due_date",
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
	# HRMS's pending_amount is what is still to be paid out, not what is still to be settled
	rows = [row for row in rows if outstanding(row) > 0]
	for row in rows:
		row.pending_amount = outstanding(row)
		row.overdue = is_due(row, scope.to_date)
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
	return create_salary_recovery(doc, salary_component, payroll_date, outstanding(doc))


def create_salary_recovery(doc, salary_component: str, payroll_date, amount: float, ignore_permissions: bool = False) -> str:
	"""Submits an Additional Salary deduction for the advance. The salary slip then reduces the net pay,
	and HRMS records the deduction as a return on the advance."""
	additional = create_return_through_additional_salary(doc)
	additional.update({"salary_component": salary_component, "payroll_date": payroll_date, "amount": amount})
	additional.flags.ignore_permissions = ignore_permissions
	additional.insert()
	additional.submit()
	return additional.name


def is_due(advance, cycle_end) -> bool:
	"""Due for recovery in a cycle: its due date, or its posting date when it has none, is on or
	before the cycle's end."""
	due = advance.get("due_date") or advance.get("posting_date")
	return bool(due) and frappe.utils.getdate(due) <= frappe.utils.getdate(cycle_end)


def recover_overdue_advances(company: str, cycle_end, force: bool = False) -> list[str]:
	"""Schedules every overdue advance of the company for deduction in the cycle that ends on
	`cycle_end`. Runs when payroll is generated for a company that recovers advances in payroll, or
	with `force` from the Advances tab. Advances with a claim still in approval, and those already
	scheduled, are skipped. Returns the Additional Salary records created."""
	from centhr.iou import settings as iou_settings
	from centhr.iou.claim import claims_in_approval

	if not force and not frappe.db.get_value("Company", company, "auto_recover_advances"):
		return []

	advances = frappe.get_all(
		"Employee Advance",
		filters={"company": company, "docstatus": 1, "paid_amount": [">", 0]},
		fields=["name", "posting_date", "due_date", "paid_amount", "claimed_amount", "return_amount"],
	)
	due = [row for row in advances if outstanding(row) > 0 and is_due(row, cycle_end)]
	if not due:
		return []

	names = [row.name for row in due]
	skipped = set(claims_in_approval(names)) | set(
		frappe.get_all(
			"Additional Salary",
			filters={"ref_doctype": "Employee Advance", "ref_docname": ["in", names], "docstatus": ["<", 2]},
			pluck="ref_docname",
		)
	)
	component = iou_settings.salary_component()
	return [
		create_salary_recovery(
			frappe.get_doc("Employee Advance", row.name), component, cycle_end, outstanding(row), ignore_permissions=True
		)
		for row in due
		if row.name not in skipped
	]


ADVANCE_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"company",
	"status",
	"docstatus",
	"posting_date",
	"due_date",
	"purpose",
	"purpose_type",
	"currency",
	"advance_amount",
	"paid_amount",
	"claimed_amount",
	"return_amount",
	"repay_unclaimed_amount_from_salary",
]


def get_advance_details(name: str) -> dict:
	"""One employee advance for the quick view: its amounts, the expense claims that settled part of
	it, and the salary deductions scheduled or made for it."""
	doc = frappe.get_doc("Employee Advance", name)
	doc.check_permission("read")
	deductions = frappe.get_all(
		"Additional Salary",
		filters={"ref_doctype": "Employee Advance", "ref_docname": name, "docstatus": ["<", 2]},
		fields=["name", "salary_component", "amount", "payroll_date", "docstatus"],
		order_by="payroll_date asc",
	)
	claims = frappe.get_all(
		"Expense Claim Advance",
		filters={"employee_advance": name, "parenttype": "Expense Claim", "docstatus": ["<", 2]},
		fields=["parent", "allocated_amount", "docstatus"],
	)
	return {
		**{field: doc.get(field) for field in ADVANCE_FIELDS},
		"outstanding_amount": outstanding(doc),
		"recovery_scheduled": bool(deductions),
		"deductions": deductions,
		"claims": claims,
	}
