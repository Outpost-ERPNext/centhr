"""The company and pay cycle every Payroll Dashboard tab works on."""

from dataclasses import dataclass
from datetime import date

import frappe
from frappe.utils import add_days, add_months, getdate

SLIP_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"company",
	"status",
	"docstatus",
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
]


@dataclass(frozen=True)
class Scope:
	company: str | None
	from_date: date
	to_date: date

	@classmethod
	def make(cls, from_date: str, to_date: str, company: str | None = None) -> "Scope":
		return cls(company or None, getdate(from_date), getdate(to_date))

	@property
	def company_filter(self) -> dict:
		return {"company": self.company} if self.company else {}

	def previous(self, months: int = 1) -> "Scope":
		"""The cycle `months` before this one; it ends the day before the following cycle starts,
		so a 20th-to-19th cycle stays one."""
		return Scope(
			self.company,
			getdate(add_months(self.from_date, -months)),
			getdate(add_days(add_months(self.from_date, -months + 1), -1)),
		)

	def get_slips(self, fields: list[str] | None = None) -> list:
		"""Salary slips of the cycle the user may read; cancelled slips are left out."""
		if not frappe.has_permission("Salary Slip", "read"):
			return []
		return frappe.get_list(
			"Salary Slip",
			filters={
				**self.company_filter,
				"docstatus": ["!=", 2],
				"start_date": ["<=", self.to_date],
				"end_date": [">=", self.from_date],
			},
			fields=fields or SLIP_FIELDS,
			order_by="employee asc",
			limit_page_length=0,
		)


def totals(slips: list) -> dict:
	return {
		"headcount": len(slips),
		"gross_pay": sum(s.gross_pay or 0 for s in slips),
		"total_deduction": sum(s.total_deduction or 0 for s in slips),
		"net_pay": sum(s.net_pay or 0 for s in slips),
	}
