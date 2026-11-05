"""Whitelisted methods of the Payroll Dashboard. Every tab takes the same company and pay cycle."""

import frappe

from centhr.api.salary_overview import SalaryOverview
from centhr.payroll_dashboard import advances, analytics, audit, compliance, processing, reports
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
