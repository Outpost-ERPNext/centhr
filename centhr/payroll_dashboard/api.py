"""Whitelisted methods of the Payroll Dashboard. Every tab takes the same company and pay cycle."""

import frappe

from centhr.api.salary_overview import SalaryOverview
from centhr.payroll_dashboard import (
	advances,
	analytics,
	audit,
	auto_attendance,
	compliance,
	master_sheet,
	payment_request,
	processing,
	reconcile,
	reminders,
	reports,
	settings,
)
from centhr.payroll_dashboard.attendance import AttendanceSummary
from centhr.payroll_dashboard.scope import Scope


@frappe.whitelist()
def get_audit(from_date: str, to_date: str, company: str | None = None) -> dict:
	return audit.PayrollAudit(Scope.make(from_date, to_date, company)).run()


@frappe.whitelist(methods=["POST"])
def set_payroll_hold(
	employee: str, from_date: str, to_date: str, reason: str | None = None, cycles: int = 1
) -> str:
	"""Hold the employee's salary from this cycle on: for `cycles` cycles, or until released when 0."""
	return audit.set_hold(employee, Scope.make(from_date, to_date), reason, cycles)


@frappe.whitelist(methods=["POST"])
def release_payroll_hold(withholding: str):
	audit.release_hold(withholding)


@frappe.whitelist(methods=["POST"])
def release_payroll_holds(withholdings: list[str] | str) -> dict:
	return audit.release_holds(parse(withholdings))


@frappe.whitelist()
def get_attendance(from_date: str, to_date: str, company: str | None = None) -> list[dict]:
	frappe.has_permission("Attendance", "read", throw=True)
	scope = Scope.make(from_date, to_date, company)
	rows = [frappe._dict(r) for r in scope.get_employees()]
	summary = AttendanceSummary(scope).summarize(rows)
	return [
		{
			key: row.get(key)
			for key in (
				"name",
				"employee_name",
				"company",
				"department",
				"designation",
				"salary_slip",
				"slip_status",
			)
		}
		| summary[row.name]
		for row in rows
	]


@frappe.whitelist()
def get_processing(from_date: str, to_date: str, company: str | None = None) -> dict:
	return processing.get_processing(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def update_salary_slips(action: str, names: list[str] | str) -> dict:
	return processing.update_slips(action, parse(names))


@frappe.whitelist(methods=["POST"])
def delete_negative_salary_slips(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""Delete the cycle's draft salary slips whose net pay is below zero."""
	return processing.delete_negative_slips(Scope.make(from_date, to_date, company))


@frappe.whitelist()
def get_payout_list(payroll_entry: str) -> dict:
	"""Who a payroll entry pays, with their bank details."""
	return processing.get_payout_list(payroll_entry)


@frappe.whitelist()
def export_payout_list(payroll_entry: str):
	processing.export_payout_list(payroll_entry)


@frappe.whitelist(methods=["POST"])
def decide_payment_request(name: str, approve: bool | int, reason: str | None = None) -> dict:
	"""Approve or reject a Payment Request Form. Only Accounts may."""
	return payment_request.decide(name, bool(frappe.utils.cint(approve)), reason)


@frappe.whitelist(methods=["POST"])
def mark_auto_attendance(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""Mark Present on the unmarked working days of employees whose salary structure asks for it."""
	return auto_attendance.mark(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def send_payroll_reminders(
	from_date: str, to_date: str, company: str | None = None, employees: list[str] | str | None = None
) -> dict:
	"""Remind employees of unmarked attendance and approvers of open leave and attendance requests."""
	return reminders.Reminders(Scope.make(from_date, to_date, company)).send(parse(employees))


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


@frappe.whitelist()
def get_obligation_breakdown(obligation: str, from_date: str, to_date: str) -> dict:
	"""The employees and salary components an obligation's liability of the cycle comes from."""
	return compliance.ObligationBreakdown(obligation, Scope.make(from_date, to_date)).run()


@frappe.whitelist()
def export_obligation_breakdown(obligation: str, from_date: str, to_date: str):
	compliance.ObligationBreakdown(obligation, Scope.make(from_date, to_date)).export()


# Settings of the chosen company


@frappe.whitelist()
def get_payroll_settings(company: str) -> dict:
	return settings.get_settings(company)


@frappe.whitelist(methods=["POST"])
def save_payroll_settings(
	company: str, start_day: int, auto_recover_advances: bool | int = False, site: dict | str | None = None
) -> dict:
	"""The company's pay cycle start day and whether payroll recovers overdue advances. `site` holds
	the calculation rules of HRMS's Payroll Settings, which apply to every company."""
	return settings.save_settings(company, start_day, bool(int(auto_recover_advances)), parse(site))


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
	master_sheet.download_template(Scope.make(from_date, to_date, company))


@frappe.whitelist()
def get_master_sheet_reconciliation(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""How the cycle's master payroll sheet compares with its salary slips."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	return reconcile.reconcile(Scope.make(from_date, to_date, company))


@frappe.whitelist(methods=["POST"])
def upload_master_sheet(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""Keep the uploaded master payroll sheet (the request's `file`) for the cycle, in place of the one
	it had, and compare it with the cycle's salary slips."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	upload = frappe.request.files.get("file")
	if not upload:
		frappe.throw(frappe._("Choose the master payroll sheet to upload."))
	scope = Scope.make(from_date, to_date, company)
	master_sheet.store(scope, upload.filename, upload.stream.read())
	return reconcile.reconcile(scope)


@frappe.whitelist(methods=["POST"])
def remove_master_sheet(from_date: str, to_date: str, company: str | None = None) -> None:
	frappe.has_permission(master_sheet.DOCTYPE, "delete", throw=True)
	master_sheet.remove(Scope.make(from_date, to_date, company))


@frappe.whitelist()
def export_master_sheet_reconciliation(
	from_date: str, to_date: str, company: str | None = None, status: str | None = None
):
	"""The reconciled rows as an Excel file: all of them, or those of one status."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	reconcile.export(Scope.make(from_date, to_date, company), status)


@frappe.whitelist()
def get_master_sheet_columns(from_date: str, to_date: str, company: str | None = None) -> dict:
	"""For Map Columns: the sheet's headers and which of them holds each thing CentHR compares."""
	frappe.has_permission("Salary Slip", "read", throw=True)
	return get_column_mapping(Scope.make(from_date, to_date, company)).as_dict()


@frappe.whitelist(methods=["POST"])
def save_master_sheet_columns(from_date: str, to_date: str, company: str, mapping: dict | str) -> dict:
	"""Save the company's column mapping and compare the cycle's sheet again with it."""
	scope = Scope.make(from_date, to_date, company)
	get_column_mapping(scope).save(frappe.parse_json(mapping) if isinstance(mapping, str) else mapping)
	return reconcile.reconcile(scope)


def get_column_mapping(scope: Scope) -> master_sheet.ColumnMapping:
	stored = master_sheet.get_stored(scope)
	if not stored:
		frappe.throw(frappe._("Upload the master sheet of this cycle first."))
	return master_sheet.ColumnMapping(scope.company, master_sheet.read_stored(stored).headers)


@frappe.whitelist()
def get_advance_details(name: str, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""With a pay cycle, also where the advance's recovery stands in it."""
	scope = Scope.make(from_date, to_date) if from_date and to_date else None
	return advances.get_advance_details(name, scope)


def parse(value):
	"""A list or dict argument arrives as JSON from a form post."""
	return frappe.parse_json(value) if isinstance(value, str) else value
