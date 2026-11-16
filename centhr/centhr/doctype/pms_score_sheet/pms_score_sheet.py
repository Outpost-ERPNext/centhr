# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from centhr.centhr.doctype.pms_settings.pms_settings import get_settings
from centhr.pms.scoring import find_band_row


class PMSScoreSheet(Document):
	def autoname(self):
		base = f"PMS-SS|{self.fiscal_year}|{self.quarter}|{self.employee}"
		name, count = base, 0
		while frappe.db.exists(self.doctype, name):
			count += 1
			name = f"{base}|{count}"
		self.name = name

	def validate(self):
		self.set_employee_details()
		self.validate_one_per_quarter()
		# A sheet migrated from the CentHR site keeps the increment that was decided there
		if not frappe.flags.centhr_migration:
			self.calculate()

	def set_employee_details(self):
		employee = frappe.db.get_value("Employee", self.employee, ["company", "department"], as_dict=True)
		self.company = employee.company
		self.department = self.department or employee.department

	def validate_one_per_quarter(self):
		filters = {
			"employee": self.employee,
			"fiscal_year": self.fiscal_year,
			"quarter": self.quarter,
			"docstatus": ["!=", 2],
			"name": ["!=", self.name],
		}
		existing = frappe.db.get_value(self.doctype, filters, "name")
		if existing:
			frappe.throw(
				_("{0} already has a Score Sheet for {1} {2}: {3}").format(
					self.employee_name or self.employee, self.quarter, self.fiscal_year, existing
				),
				title=_("Already Exists"),
			)

	def calculate(self):
		"""The increment band the final score falls in, and the CTC it gives."""
		band = find_band_row(self.final_score, get_settings(self.company).increments)
		self.outcome = band.status if band else None
		self.increment = flt((band.increment_ or "").replace("%", "")) if self.outcome == "Increment" else 0
		if self.docstatus == 0:
			self.old_ctc, self.currency = get_current_ctc(self.employee)
		self.new_ctc = flt(self.old_ctc) * (1 + self.increment / 100)
		self.ctc_impact = self.new_ctc - flt(self.old_ctc)

	@property
	def final_score(self) -> float:
		"""HR's normalized score when they chose to use one, the overall score otherwise."""
		return flt(self.normalized_score if self.check_normalized_score else self.calculated_score)

	def before_submit(self):
		self.status = "Approved"

	def reject(self) -> None:
		if self.docstatus != 0:
			frappe.throw(_("Only a Score Sheet that is not approved yet can be rejected."))
		self.status = "Rejected"
		self.save()


def get_current_ctc(employee: str) -> tuple[float, str | None]:
	"""Base and currency of the employee's latest submitted Salary Structure Assignment."""
	rows = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": employee, "docstatus": 1},
		fields=["base", "currency"],
		order_by="from_date desc",
		limit=1,
	)
	return (flt(rows[0].base), rows[0].currency) if rows else (0.0, None)
