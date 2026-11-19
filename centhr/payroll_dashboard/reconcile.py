"""Excel reconciliation: the cycle's master payroll sheet against its salary slips."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import flt, fmt_money
from frappe.utils.xlsxutils import build_xlsx_response

from centhr.payroll_dashboard import master_sheet
from centhr.payroll_dashboard.master_sheet import COMPARED, ColumnMapping
from centhr.payroll_dashboard.scope import Scope

AMOUNT_TOLERANCE = 0.05
DAYS_TOLERANCE = 0.1
STATUSES = ("Matched", "Discrepancy", "Missing in Excel", "Missing in ERP")
LABELS = {
	"net_pay": "Net pay",
	"gross_pay": "Gross pay",
	"total_deduction": "Total deduction",
	"payment_days": "Payment days",
}
EXPORT_HEADERS = [
	"Employee ID",
	"Employee Name",
	"Department",
	"ERP Net Pay",
	"Excel Net Pay",
	"Variance",
	"ERP Gross Pay",
	"Excel Gross Pay",
	"ERP Total Deduction",
	"Excel Total Deduction",
	"ERP Payment Days",
	"Excel Payment Days",
	"Status",
	"Differences & Remarks",
]


def reconcile(scope: Scope) -> dict:
	"""How the cycle's master sheet compares with its salary slips; `sheet` is None before one is uploaded."""
	stored = master_sheet.get_stored(scope)
	return Reconciliation(scope, stored).run() if stored else {"sheet": None}


def export(scope: Scope, status: str | None = None) -> None:
	"""The reconciled rows as an Excel file: all of them, or those of one status."""
	result = reconcile(scope)
	if not result.get("rows"):
		frappe.throw(result.get("problem") or _("Upload the master sheet of this cycle first."))
	rows = [row for row in result["rows"] if not status or row["status"] == status]
	data = [
		[
			row["employee"],
			row["employee_name"],
			row["department"],
			row["erp_net_pay"],
			row["excel_net_pay"],
			row["variance"],
			row["erp_gross_pay"],
			row["excel_gross_pay"],
			row["erp_total_deduction"],
			row["excel_total_deduction"],
			row["erp_payment_days"],
			row["excel_payment_days"],
			row["status"],
			"; ".join(row["remarks"]),
		]
		for row in rows
	]
	build_xlsx_response(
		[EXPORT_HEADERS, *data],
		f"Payroll reconciliation {status or 'All records'} {scope.from_date} to {scope.to_date}",
	)


class Reconciliation:
	"""Each employee of the sheet and of the cycle's salary slips, with what differs between the two."""

	def __init__(self, scope: Scope, stored):
		self.stored = stored
		self.sheet = master_sheet.read_stored(stored)
		self.mapping = ColumnMapping(scope.company, self.sheet.headers)
		self.excel = {} if self.mapping.missing else self.sheet.parse(self.mapping)
		self.slips = {slip.employee: slip for slip in scope.get_slips()}
		self.components = ComponentAmounts([slip.name for slip in self.slips.values()])

	def run(self) -> dict:
		rows = self.compare_all() if self.excel else []
		statuses = [row["status"] for row in rows]
		return {
			"sheet": master_sheet.describe(self.stored),
			"problem": self.problem,
			"rows": sorted(rows, key=lambda row: (row["status"] == "Matched", row["employee"])),
			"summary": {
				"excel": len(self.excel),
				"slips": len(self.slips),
				**{status: statuses.count(status) for status in STATUSES},
			},
			"ignored": self.sheet.blank,
		}

	@property
	def problem(self) -> str | None:
		"""Why the sheet cannot be compared yet."""
		if self.mapping.missing:
			return _("Map these columns of the sheet to compare it: {0}.").format(
				", ".join(self.mapping.missing)
			)
		if not self.excel:
			return _("No row of the sheet has a Net Pay amount, so there is nothing to compare.")
		return None

	def compare_all(self) -> list[dict]:
		slips = dict(self.slips)
		by_number = get_employee_numbers(list(slips))
		rows = []
		for key, excel in self.excel.items():
			# Finance may list the old employee number instead of the CentHR ID
			employee = key if key in slips else by_number.get(key, key)
			rows.append(self.compare(employee, slips.pop(employee, None), excel))
		return rows + [self.compare(employee, slip, None) for employee, slip in slips.items()]

	def compare(self, employee: str, slip, excel: dict | None) -> dict:
		row = {
			"employee": employee,
			"employee_name": slip.employee_name if slip else None,
			"department": slip.department if slip else None,
			"salary_slip": slip.name if slip else None,
			"currency": slip.currency if slip else None,
			"differences": [],
			"components": [],
		}
		for key in COMPARED:
			row[f"erp_{key}"] = flt(slip.get(key)) if slip else None
			row[f"excel_{key}"] = excel.get(key) if excel else None

		if slip and excel:
			row["differences"] = [
				key for key in COMPARED if differs(key, row[f"erp_{key}"], row[f"excel_{key}"])
			]
			row["components"] = self.compare_components(slip, excel["components"])
		row["variance"] = flt(row["erp_net_pay"]) - flt(row["excel_net_pay"]) if slip and excel else None
		row["status"] = get_status(slip, excel, row["differences"])
		row["remarks"] = get_remarks(row)
		return row

	def compare_components(self, slip, excel: dict[str, float | None]) -> list[dict]:
		"""The slip's salary components beside their columns of the sheet. They explain a difference;
		the status comes from the totals alone."""
		lines = []
		for target in self.mapping.components:
			erp = self.components.get(slip.name, target.key)
			column = self.mapping.active[target.key]
			amount = excel.get(target.key)
			if not erp and not amount:
				continue
			variance = erp - flt(amount) if column else None
			lines.append(
				{
					"component": target.label,
					"type": target.type,
					"erp": erp,
					"column": column,
					"excel": amount,
					"variance": variance,
					"differs": variance is not None and abs(variance) > AMOUNT_TOLERANCE,
				}
			)
		return lines


class ComponentAmounts:
	"""What each salary slip pays or deducts per salary component."""

	def __init__(self, slips: list[str]):
		self.amounts = defaultdict(float)
		if not slips:
			return
		for line in frappe.get_all(
			"Salary Detail",
			filters={
				"parenttype": "Salary Slip",
				"parent": ["in", slips],
				"parentfield": ["in", ["earnings", "deductions"]],
			},
			fields=["parent", "salary_component", "amount"],
		):
			self.amounts[(line.parent, line.salary_component)] += flt(line.amount)

	def get(self, slip: str, component: str) -> float:
		return self.amounts.get((slip, component), 0.0)


def get_status(slip, excel: dict | None, differences: list[str]) -> str:
	if not slip:
		return "Missing in ERP"
	if excel is None:
		return "Missing in Excel"
	return "Discrepancy" if differences else "Matched"


def get_remarks(row: dict) -> list[str]:
	if row["status"] == "Missing in ERP":
		return [_("In the sheet, but has no salary slip in this cycle")]
	if row["status"] == "Missing in Excel":
		return [_("Has a salary slip, but is not in the sheet")]
	if row["status"] == "Matched":
		return [_("All amounts and days match")]
	return [
		_("{0} differs: ERP {1} vs Excel {2}").format(
			_(LABELS[key]),
			show(key, row[f"erp_{key}"], row["currency"]),
			show(key, row[f"excel_{key}"], row["currency"]),
		)
		for key in row["differences"]
	]


def show(key: str, value: float, currency: str | None) -> str:
	return f"{flt(value):g}" if key == "payment_days" else fmt_money(value, currency=currency)


def differs(key: str, erp: float | None, excel: float | None) -> bool:
	"""A column the sheet leaves empty is not compared."""
	if excel is None:
		return False
	tolerance = DAYS_TOLERANCE if key == "payment_days" else AMOUNT_TOLERANCE
	return abs(flt(erp) - flt(excel)) > tolerance


def get_employee_numbers(employees: list[str]) -> dict[str, str]:
	if not employees:
		return {}
	rows = frappe.get_all(
		"Employee",
		filters={"name": ["in", employees], "employee_number": ["is", "set"]},
		fields=["employee_number", "name"],
		as_list=True,
	)
	return dict(rows)
