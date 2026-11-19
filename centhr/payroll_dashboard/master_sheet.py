"""Finance's master payroll sheet: one kept per pay cycle, how it is read, and which column is what."""

import json
import re
from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.csvutils import read_csv_content
from frappe.utils.xlsxutils import build_xlsx_response, read_xlsx_file_from_attached_file

from centhr.payroll_dashboard.scope import Scope

DOCTYPE = "Payroll Master Sheet"
MAPPING_FIELD = "payroll_master_sheet_columns"
TEMPLATE_HEADERS = ["Employee ID", "Employee Name", "Payment Days", "Gross Pay", "Total Deduction", "Net Pay"]
# What a slip is compared on, besides its salary components
COMPARED = ("net_pay", "gross_pay", "total_deduction", "payment_days")


@dataclass(frozen=True)
class Target:
	"""Something CentHR compares, which a column of the sheet can be mapped to. `aliases` are the
	header texts it is recognised by, lower case with spaces and punctuation left out."""

	key: str
	label: str
	type: str
	aliases: tuple[str, ...]
	required: bool = False


FIELD_TARGETS = (
	Target(
		"employee",
		"Employee ID",
		"Field",
		("employeeid", "employee", "employeeno", "employeenumber", "employeecode", "staffid", "empid", "id"),
		required=True,
	),
	Target(
		"net_pay",
		"Net Pay",
		"Field",
		("netpay", "net", "netsalary", "netamount", "nettopay", "takehome"),
		True,
	),
	Target("gross_pay", "Gross Pay", "Field", ("grosspay", "gross", "grosssalary", "totalgross")),
	Target(
		"total_deduction",
		"Total Deduction",
		"Field",
		("totaldeduction", "totaldeductions", "deductions", "deduction"),
	),
	Target(
		"payment_days", "Payment Days", "Field", ("paymentdays", "paydays", "paiddays", "daysworked", "days")
	),
)


# The sheet kept for a cycle


def get_stored(scope: Scope):
	"""The master sheet uploaded for the cycle, if any."""
	name = frappe.db.get_value(
		DOCTYPE,
		{
			"company": scope.company or ["is", "not set"],
			"from_date": scope.from_date,
			"to_date": scope.to_date,
		},
	)
	return frappe.get_doc(DOCTYPE, name) if name else None


def store(scope: Scope, filename: str, content: bytes):
	"""Keep the uploaded sheet for the cycle, in place of the one it had."""
	frappe.has_permission(DOCTYPE, "create", throw=True)
	# A file that cannot be read is refused before the cycle's sheet is replaced
	MasterSheet(filename, content)
	remove(scope)
	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"company": scope.company,
			"from_date": scope.from_date,
			"to_date": scope.to_date,
			"file_name": filename,
		}
	).insert()
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": DOCTYPE,
			"attached_to_name": doc.name,
			"attached_to_field": "file",
		}
	).insert(ignore_permissions=True)
	doc.db_set("file", file.file_url)
	return doc


def remove(scope: Scope) -> None:
	stored = get_stored(scope)
	if stored:
		# Its file goes with it
		stored.delete()


def read_stored(stored) -> "MasterSheet":
	file = frappe.get_doc("File", {"attached_to_doctype": DOCTYPE, "attached_to_name": stored.name})
	return MasterSheet(stored.file_name, file.get_content())


def describe(stored) -> dict:
	file = frappe.db.get_value(
		"File", {"attached_to_doctype": DOCTYPE, "attached_to_name": stored.name}, ["file_size"], as_dict=True
	)
	return {
		"file_name": stored.file_name,
		"file_url": stored.file,
		"file_size": file.file_size if file else None,
		"uploaded_on": stored.creation,
		"uploaded_by": frappe.db.get_value("User", stored.owner, "full_name") or stored.owner,
	}


def download_template(scope: Scope) -> None:
	"""The sheet Finance fills in: one row per employee who has a salary slip in the cycle."""
	slips = scope.get_slips(["employee", "employee_name"])
	rows = [[slip.employee, slip.employee_name, None, None, None, None] for slip in slips]
	build_xlsx_response(
		[TEMPLATE_HEADERS, *rows], f"Payroll master sheet {scope.from_date} to {scope.to_date}"
	)


class MasterSheet:
	"""The sheet's cells: its first row names the columns, each later row is one employee."""

	def __init__(self, filename: str, content: bytes | str):
		rows = self.read(filename, content)
		if len(rows) < 2:
			frappe.throw(_("The sheet has no rows under its header row."), title=_("Empty Sheet"))
		self.headers = [str(cell or "").strip() for cell in rows[0]]
		self.body = rows[1:]
		self.blank = 0

	def read(self, filename: str, content: bytes | str) -> list[list]:
		if filename.lower().endswith(".csv"):
			return read_csv_content(content)
		if filename.lower().endswith(".xlsx"):
			return read_xlsx_file_from_attached_file(fcontent=content)
		frappe.throw(_("Upload an .xlsx or .csv file."), title=_("Unsupported File"))

	def parse(self, mapping: "ColumnMapping") -> dict[str, dict]:
		"""Rows by employee. A row without a net pay is one Finance has not filled in, such as an
		untouched row of the template, so it is counted in `blank` and not compared."""
		index = {key: self.headers.index(header) for key, header in mapping.active.items() if header}
		components = [target.key for target in mapping.components if target.key in index]
		parsed = {}
		self.blank = 0
		for row in self.body:
			employee = as_id(cell(row, index.get("employee")))
			if not employee:
				continue
			if as_number(cell(row, index.get("net_pay"))) is None:
				self.blank += 1
				continue
			parsed[employee] = {
				**{key: as_number(cell(row, index[key])) for key in COMPARED if key in index},
				"components": {key: as_number(cell(row, index[key])) for key in components},
			}
		return parsed


class ColumnMapping:
	"""Which column of the sheet holds each thing CentHR compares. A column is recognised by its
	header; what HR chose in Map Columns for the company wins while the sheet has that header."""

	def __init__(self, company: str | None, headers: list[str]):
		self.company = company
		self.headers = list(dict.fromkeys(header for header in headers if header))
		self.components = get_component_targets()
		self.targets = [*FIELD_TARGETS, *self.components]
		self.auto = {target.key: self.recognise(target) for target in self.targets}
		self.active = {**self.auto, **self.get_saved()}

	def recognise(self, target: Target) -> str | None:
		by_name = {normalise(header): header for header in reversed(self.headers)}
		return next((by_name[alias] for alias in target.aliases if alias in by_name), None)

	def get_saved(self) -> dict[str, str | None]:
		"""HR's choices that still fit this sheet. An empty choice is a column unmapped on purpose."""
		if not self.company:
			return {}
		saved = json.loads(frappe.db.get_value("Company", self.company, MAPPING_FIELD) or "{}")
		return {
			key: header or None
			for key, header in saved.items()
			if key in self.auto and (not header or header in self.headers)
		}

	@property
	def missing(self) -> list[str]:
		"""Columns the comparison cannot do without, and that no header was recognised for."""
		return [target.label for target in self.targets if target.required and not self.active[target.key]]

	def save(self, chosen: dict[str, str]) -> None:
		"""Keep what differs from the recognised columns, so a later sheet is still recognised by itself."""
		if not self.company:
			frappe.throw(_("Choose a company to save its column mapping."))
		frappe.has_permission(DOCTYPE, "write", throw=True)
		frappe.has_permission("Company", "read", doc=self.company, throw=True)
		unknown = [header for header in chosen.values() if header and header not in self.headers]
		if unknown:
			frappe.throw(_("The sheet has no column {0}.").format(", ".join(unknown)))
		changed = {
			key: header or ""
			for key, header in chosen.items()
			if key in self.auto and (header or None) != self.auto[key]
		}
		# HR runs payroll without rights on the Company record itself
		frappe.db.set_value("Company", self.company, MAPPING_FIELD, json.dumps(changed))

	def as_dict(self) -> dict:
		return {
			"headers": self.headers,
			"targets": [
				{"key": t.key, "label": t.label, "type": t.type, "required": t.required} for t in self.targets
			],
			"mapping": self.active,
			"auto": self.auto,
		}


def get_component_targets() -> list[Target]:
	"""Salary components, earnings first. One is recognised by its name or its abbreviation."""
	components = frappe.get_all(
		"Salary Component",
		filters={"disabled": 0},
		fields=["name", "salary_component_abbr", "type"],
		order_by="type desc, name asc",
	)
	return [
		Target(
			c.name,
			c.name,
			c.type,
			tuple(filter(None, (normalise(c.name), long_enough(normalise(c.salary_component_abbr))))),
		)
		for c in components
	]


# Cells


def cell(row: list, index: int | None):
	return row[index] if index is not None and index < len(row) else None


def as_id(value) -> str:
	"""Excel hands a numeric ID over as a number, 1001.0 for 1001."""
	if isinstance(value, float) and value.is_integer():
		value = int(value)
	return str(value or "").strip()


def as_number(value) -> float | None:
	"""The amount in a cell, whatever currency sign or thousands separator it is written with."""
	if isinstance(value, (int, float)):
		return flt(value)
	digits = re.sub(r"[^0-9.\-]", "", str(value or ""))
	try:
		return float(digits)
	except ValueError:
		return None


def normalise(value) -> str:
	return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def long_enough(abbreviation: str) -> str | None:
	"""A one-letter abbreviation is too easily some other column's header."""
	return abbreviation if len(abbreviation) > 1 else None
