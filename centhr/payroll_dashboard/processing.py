"""Payroll Processing tab: the cycle's totals against the last cycle, its payroll entries and salary slips."""

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.xlsxutils import build_xlsx_response

from centhr.api.payroll import get_payroll_runs
from centhr.payroll_dashboard import confidential
from centhr.payroll_dashboard.scope import Scope, totals

SLIP_ACTIONS = ("submit", "recalculate", "delete")
PAYOUT_HEADERS = ["Employee ID", "Employee Name", "Department", "Paid By", "Bank", "Account Number", "Net Pay", "Status"]


def get_processing(scope: Scope) -> dict:
	slips = scope.get_slips()
	add_advance_deductions(slips)
	current, previous = totals(slips), totals(scope.previous().get_slips())
	return {
		"totals": current,
		"previous": previous,
		"runs": get_payroll_runs(str(scope.from_date), str(scope.to_date), scope.company),
		"slips": slips,
		# Confidential structure -> batch, for the batches this user may run
		"confidential_batches": confidential.get_visible_batches(scope.company) if scope.company else {},
	}


def add_advance_deductions(slips: list) -> None:
	"""`iou_deduction` on each slip: what it deducts to recover employee advances (IOUs), which is
	not a cost of the salary itself."""
	amounts = get_advance_deductions([slip.name for slip in slips])
	for slip in slips:
		slip.iou_deduction = amounts.get(slip.name, 0)


def get_advance_deductions(slips: list[str]) -> dict[str, float]:
	component = frappe.db.get_single_value("CentHr Settings", "iou_salary_component")
	if not component or not slips:
		return {}
	amounts: dict[str, float] = {}
	for line in frappe.get_all(
		"Salary Detail",
		filters={
			"parenttype": "Salary Slip",
			"parent": ["in", slips],
			"parentfield": "deductions",
			"salary_component": component,
		},
		fields=["parent", "amount"],
	):
		amounts[line.parent] = amounts.get(line.parent, 0) + flt(line.amount)
	return amounts


def get_payout_list(payroll_entry: str) -> dict:
	"""Who a payroll entry pays, how and how much. An employee paid by bank without an account
	number is flagged, as the bank cannot pay them."""
	entry = frappe.get_doc("Payroll Entry", payroll_entry)
	entry.check_permission("read")
	slips = frappe.get_list(
		"Salary Slip",
		filters={"payroll_entry": payroll_entry, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"employee",
			"employee_name",
			"department",
			"status",
			"currency",
			"net_pay",
			"mode_of_payment",
			"bank_name",
			"bank_account_no",
		],
		order_by="employee asc",
		limit_page_length=0,
	)
	modes = dict(
		frappe.get_all(
			"Employee",
			filters={"name": ["in", [slip.employee for slip in slips] or [""]]},
			fields=["name", "salary_mode"],
			as_list=True,
		)
	)
	for slip in slips:
		slip.paid_by = slip.mode_of_payment or modes.get(slip.employee)
		slip.missing_account = slip.paid_by == "Bank" and not slip.bank_account_no
	return {
		"payroll_entry": entry.name,
		"rows": slips,
		"total": sum(flt(slip.net_pay) for slip in slips),
		"missing_accounts": sum(1 for slip in slips if slip.missing_account),
	}


def export_payout_list(payroll_entry: str) -> None:
	payouts = get_payout_list(payroll_entry)
	data = [
		[
			row.employee,
			row.employee_name,
			row.department,
			row.paid_by,
			row.bank_name,
			row.bank_account_no,
			row.net_pay,
			row.status,
		]
		for row in payouts["rows"]
	]
	build_xlsx_response([PAYOUT_HEADERS, *data], f"Payout list {payroll_entry}")


def update_slips(action: str, names: list[str]) -> dict:
	"""Runs `action` on each draft slip; one failure does not stop the others."""
	if action not in SLIP_ACTIONS:
		frappe.throw(_("Unknown action {0}.").format(action))
	done, failed = [], []
	for name in names:
		frappe.db.savepoint("slip_action")
		try:
			run_slip_action(action, name)
			done.append(name)
		except Exception as e:
			frappe.db.rollback(save_point="slip_action")
			failed.append({"name": name, "error": frappe.utils.strip_html(str(e))})
	frappe.clear_messages()
	return {"done": done, "failed": failed}


def delete_negative_slips(scope: Scope) -> dict:
	"""Delete the cycle's draft salary slips that pay less than nothing, so they can be corrected and
	generated again. A slip of exactly zero can be right, such as a month of unpaid leave, so it stays."""
	negative = [slip.name for slip in scope.get_slips() if slip.docstatus == 0 and (slip.net_pay or 0) < 0]
	return update_slips("delete", negative)


def run_slip_action(action: str, name: str):
	doc = frappe.get_doc("Salary Slip", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft salary slips can be changed."))
	if action == "delete":
		doc.delete()
	elif action == "submit":
		doc.submit()
	else:
		# Saving a draft slip makes HRMS work its days and amounts out again
		doc.save()


SLIP_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"designation",
	"company",
	"status",
	"docstatus",
	"start_date",
	"end_date",
	"salary_structure",
	"payroll_entry",
	"journal_entry",
	"currency",
	"total_working_days",
	"payment_days",
	"absent_days",
	"leave_without_pay",
	"gross_pay",
	"total_deduction",
	"net_pay",
	"bank_name",
	"bank_account_no",
]


def get_slip_details(name: str) -> dict:
	"""One salary slip for the quick view: its days, earnings, deductions and net pay."""
	doc = frappe.get_doc("Salary Slip", name)
	doc.check_permission("read")
	return {
		**{field: doc.get(field) for field in SLIP_FIELDS},
		"earnings": component_lines(doc.earnings),
		"deductions": component_lines(doc.deductions),
		# The quick view shows this deduction apart: it recovers an advance, it is not a cost of the salary
		"iou_component": frappe.db.get_single_value("CentHr Settings", "iou_salary_component"),
	}


def component_lines(rows: list) -> list[dict]:
	return [{"salary_component": row.salary_component, "amount": row.amount} for row in rows]
