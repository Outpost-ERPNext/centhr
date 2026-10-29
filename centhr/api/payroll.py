import frappe
from frappe import _

from centhr.api.payroll_run import PayrollGenerator, PayrollRun


@frappe.whitelist()
def get_payroll_runs(company: str, start_date: str, end_date: str) -> list[dict]:
	"""The period's payroll entries, each with the step it waits for."""
	names = frappe.get_list(
		"Payroll Entry",
		filters={
			"company": company,
			"start_date": [">=", start_date],
			"end_date": ["<=", end_date],
			"docstatus": ["!=", 2],
		},
		order_by="creation desc",
		pluck="name",
	)
	return [PayrollRun(name).summary() for name in names]


@frappe.whitelist(methods=["POST"])
def generate_payroll(company: str, start_date: str, end_date: str) -> dict:
	"""Creates and submits a monthly Payroll Entry for the period. On submit, HRMS creates the draft
	salary slips (in a background job for more than 30 employees)."""
	name = PayrollGenerator(company, start_date, end_date).run()
	return PayrollRun(name).summary()


@frappe.whitelist(methods=["POST"])
def run_payroll_step(payroll_entry: str, step: str, payment_account: str | None = None) -> dict:
	"""Runs one step of a payroll run and returns the run as it is now."""
	PayrollRun(payroll_entry).run_step(step, payment_account)
	return PayrollRun(payroll_entry).summary()


@frappe.whitelist(methods=["POST"])
def fill_payroll_employees(payroll_entry: str) -> list[dict] | None:
	"""Fills a draft Payroll Entry's employees and saves it, as the "Get Employees" button does in Desk.
	Returns the employees with unmarked attendance when the entry validates attendance."""
	doc = frappe.get_doc("Payroll Entry", payroll_entry)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Employees can only be fetched for a draft Payroll Entry."))
	unmarked = doc.fill_employee_details()
	doc.save()
	return unmarked
