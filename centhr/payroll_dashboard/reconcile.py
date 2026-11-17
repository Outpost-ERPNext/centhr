"""Excel reconciliation: Finance's master payroll sheet against the cycle's salary slips."""

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import build_xlsx_response, read_xlsx_file_from_attached_file

from centhr.payroll_dashboard.scope import Scope

# Column of the sheet -> header texts it is recognised by (lower case, spaces and punctuation ignored)
COLUMNS = {
	"employee": ("employeeid", "employee", "employeeno", "employeenumber", "staffid", "empid", "id"),
	"net_pay": ("netpay", "net", "netsalary", "nettopay", "takehome"),
	"gross_pay": ("grosspay", "gross", "grosssalary"),
	"total_deduction": ("totaldeduction", "totaldeductions", "deductions", "deduction"),
	"payment_days": ("paymentdays", "paydays", "daysworked", "days"),
}
TEMPLATE_HEADERS = ["Employee ID", "Employee Name", "Payment Days", "Gross Pay", "Total Deduction", "Net Pay"]
AMOUNT_TOLERANCE = 0.05
DAYS_TOLERANCE = 0.1
COMPARED = ("net_pay", "gross_pay", "total_deduction", "payment_days")


def download_template(scope: Scope) -> None:
	"""The sheet Finance fills in: one row per employee who has a salary slip in the cycle."""
	slips = scope.get_slips(["employee", "employee_name"])
	rows = [[slip.employee, slip.employee_name, None, None, None, None] for slip in slips]
	build_xlsx_response(
		[TEMPLATE_HEADERS, *rows], f"Payroll master sheet {scope.from_date} to {scope.to_date}"
	)


class MasterSheet:
	"""The uploaded sheet: its first row names the columns, each later row is one employee."""

	def __init__(self, filename: str, content: bytes):
		rows = self.read(filename, content)
		if len(rows) < 2:
			frappe.throw(_("The sheet has no rows under its header row."), title=_("Empty Sheet"))
		self.columns = self.find_columns(rows[0])
		self.rows = self.parse(rows[1:])

	def read(self, filename: str, content: bytes) -> list[list]:
		if filename.lower().endswith(".csv"):
			return read_csv_content(content)
		if filename.lower().endswith(".xlsx"):
			return read_xlsx_file_from_attached_file(fcontent=content)
		frappe.throw(_("Upload an .xlsx or .csv file."), title=_("Unsupported File"))

	def find_columns(self, header: list) -> dict[str, int]:
		names = [normalise(cell) for cell in header]
		columns = {
			key: names.index(alias) for key, aliases in COLUMNS.items() for alias in aliases if alias in names
		}
		missing = [
			label
			for key, label in (("employee", "Employee ID"), ("net_pay", "Net Pay"))
			if key not in columns
		]
		if missing:
			frappe.throw(
				_("The sheet needs these columns in its first row: {0}.").format(", ".join(missing)),
				title=_("Columns Missing"),
			)
		return columns

	def parse(self, rows: list[list]) -> dict[str, dict]:
		"""Rows by employee. A row without a net pay is one Finance has not filled in, such as an
		untouched row of the template, so it is counted in `blank` and not compared."""
		parsed = {}
		self.blank = 0
		for row in rows:
			employee = str(self.cell(row, "employee") or "").strip()
			if not employee:
				continue
			if self.number(row, "net_pay") is None:
				self.blank += 1
				continue
			parsed[employee] = {key: self.number(row, key) for key in COMPARED if key in self.columns}
		if not parsed:
			frappe.throw(
				_("No row of the sheet has a Net Pay amount, so there is nothing to compare."),
				title=_("Sheet Not Filled In"),
			)
		return parsed

	def cell(self, row: list, key: str):
		index = self.columns[key]
		return row[index] if index < len(row) else None

	def number(self, row: list, key: str) -> float | None:
		value = self.cell(row, key)
		if value in (None, ""):
			return None
		return flt(str(value).replace(",", ""))


def reconcile(scope: Scope, filename: str, content: bytes) -> dict:
	"""Each employee of the sheet and of the cycle's salary slips, with what differs between the two."""
	sheet = MasterSheet(filename, content)
	slips = {slip.employee: slip for slip in scope.get_slips()}
	by_number = get_employee_numbers(list(slips))

	rows = []
	for key, excel in sheet.rows.items():
		# Finance may list the old employee number instead of the CentHR ID
		employee = key if key in slips else by_number.get(key, key)
		rows.append(compare(employee, slips.pop(employee, None), excel))
	rows += [compare(employee, slip, None) for employee, slip in slips.items()]

	statuses = [row["status"] for row in rows]
	return {
		"rows": sorted(rows, key=lambda row: (row["status"] == "Matched", row["employee"])),
		"summary": {
			status: statuses.count(status)
			for status in ("Matched", "Discrepancy", "Missing in Excel", "Missing in ERP")
		},
		"columns": sorted(sheet.columns),
		"ignored": sheet.blank,
	}


def compare(employee: str, slip, excel: dict | None) -> dict:
	row = {
		"employee": employee,
		"employee_name": slip.employee_name if slip else None,
		"salary_slip": slip.name if slip else None,
		"currency": slip.currency if slip else None,
	}
	for key in COMPARED:
		row[f"erp_{key}"] = flt(slip.get(key)) if slip else None
		row[f"excel_{key}"] = excel.get(key) if excel else None

	if not slip:
		row["status"] = "Missing in ERP"
	elif excel is None:
		row["status"] = "Missing in Excel"
	else:
		row["differences"] = [key for key in COMPARED if differs(key, row[f"erp_{key}"], row[f"excel_{key}"])]
		row["status"] = "Discrepancy" if row["differences"] else "Matched"
	row["variance"] = flt(row["erp_net_pay"]) - flt(row["excel_net_pay"]) if slip and excel else None
	return row


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


def normalise(value) -> str:
	return "".join(ch for ch in str(value or "").lower() if ch.isalnum())
