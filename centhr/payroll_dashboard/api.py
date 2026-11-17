"""Whitelisted methods of the Payroll Dashboard. Every tab takes the same company and pay cycle."""

import frappe

from centhr.api.salary_overview import SalaryOverview
from centhr.payroll_dashboard import (
	advances,
	analytics,
	audit,
	compliance,
	processing,
	reconcile,
	reports,
	settings,
)
from centhr.payroll_dashboard.attendance import AttendanceSummary
from centhr.payroll_dashboard.scope import Scope


@frappe.whitelist()
def get_audit(from_date: str, to_date: str, company: str | None = None) -> dict:
	return audit.PayrollAudit(Scope.make(from_date, to_date, company)).run()


@frappe.whitelist(methods=["POST"])
def set_payroll_hold(employee: str, from_date: str, to_date: str, reason: str | None = None) -> str:
	return audit.set_hold(employee, Scope.make(from_date, to_date), reason)


@frappe.whitelist(methods=["POST"])
def release_payroll_hold(withholding: str):
	audit.release_hold(withholding)


@frappe.whitelist()
def get_attendance(from_date: str, to_date: str, company: str | None = None) -> list[dict]:
	frappe.has_permission("Attendance", "read", throw=True)
	scope = Scope.make(from_date, to_date, company)
	rows = [frappe._dict(r) for r in SalaryOverview(company, scope.from_date, scope.to_date).get_rows()]
	summary = AttendanceSummary(scope).summarize(rows)
	return [
		{key: row.get(key) for key in ("name", "employee_name", "company", "department", "designation", "salary_slip", "slip_status")}
		| summary[row.name]
		for row in rows
	]


@frappe.whitelist()
def get_processing(from_date: str, to_date: str, company: str | None = None) -> dict:
	return processing.get_processing(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def update_salary_slips(action: str, names: list[str] | str) -> dict:
	return processing.update_slips(action, frappe.parse_json(names) if isinstance(names, str) else names)


@frappe.whitelist()
def get_analytics(view: str, from_date: str, to_date: str, company: str | None = None) -> dict:
	return analytics.get_analytics(Scope.make(from_date, to_date, company), view)


@frappe.whitelist()
def get_advances(from_date: str, to_date: str, company: str | None = None) -> dict:
	return advances.get_advances(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def recover_advance(advance: str, salary_component: str, payroll_date: str) -> str:
	return advances.recover_advance(advance, salary_component, payroll_date)


@frappe.whitelist()
def get_reports() -> list[dict]:
	return reports.get_reports()


@frappe.whitelist()
def get_compliance(from_date: str, to_date: str, company: str | None = None) -> dict:
	return compliance.get_compliance(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def request_obligation_payment(obligation: str, amount: float, payment_account: str | None = None) -> str:
	return compliance.request_payment(obligation, amount, payment_account)


# Settings of the chosen company


@frappe.whitelist()
def get_payroll_settings(company: str) -> dict:
	return settings.get_settings(company)


@frappe.whitelist(methods=["POST"])
def save_payroll_settings(company: str, start_day: int, auto_recover_advances: bool | int = False) -> dict:
	"""The company's pay cycle start day and whether payroll recovers overdue advances."""
	return settings.save_settings(company, start_day, bool(int(auto_recover_advances)))


@frappe.whitelist(methods=["POST"])
def recover_overdue_advances(company: str, to_date: str) -> int:
	"""Schedule every overdue advance of the company for deduction in the cycle ending on `to_date`."""
	frappe.has_permission("Additional Salary", "create", throw=True)
	frappe.has_permission("Company", "read", doc=company, throw=True)
	return len(advances.recover_overdue_advances(company, to_date, force=True))


# Salary slip quick view and Excel reconciliation


@frappe.whitelist()
def get_salary_slip_details(name: str) -> dict:
	return processing.get_slip_details(name)


@frappe.whitelist()
def download_master_sheet_template(from_date: str, to_date: str, company: str | None = None):
	"""The Excel sheet Finance fills in for the reconciliation, with the cycle's employees listed."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	reconcile.download_template(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def reconcile_master_sheet(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""Compare the uploaded master payroll sheet (the request's `file`) with the cycle's salary slips.
	Nothing is saved: the result goes back to the page."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	upload = frappe.request.files.get("file")
	if not upload:
		frappe.throw(frappe._("Choose the master payroll sheet to upload."))
	return reconcile.reconcile(Scope.make(from_date, to_date, company), upload.filename, upload.stream.read())


@frappe.whitelist()
def get_advance_details(name: str) -> dict:
	return advances.get_advance_details(name)
