"""The month a KPI Template and its KPI Result are for."""

from dataclasses import dataclass
from datetime import date

import frappe
from erpnext.accounts.utils import get_fiscal_year
from frappe import _
from frappe.utils import add_months, get_last_day, getdate

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@dataclass(frozen=True)
class KpiMonth:
	fiscal_year: str
	month: str

	@classmethod
	def of(cls, day: date | str, company: str) -> "KpiMonth":
		"""The KPI month a day falls in, in the fiscal year the company has for that day."""
		day = getdate(day)
		return cls(get_fiscal_year(day, company=company)[0], MONTHS[day.month - 1])

	@property
	def number(self) -> int:
		return MONTHS.index(self.month) + 1

	@property
	def start(self) -> date:
		"""First day of the month. The fiscal year decides the calendar year: in an April to March
		year, Jan belongs to the second calendar year."""
		year_start, year_end = frappe.get_cached_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"]
		)
		for year in range(year_start.year, year_end.year + 1):
			first = date(year, self.number, 1)
			if get_last_day(first) >= year_start and first <= year_end:
				return first
		frappe.throw(_("{0} is not a month of Fiscal Year {1}.").format(self.month, self.fiscal_year))

	def starts_by(self, day: date) -> bool:
		return self.start <= day

	def freeze_date(self, freeze_day: int) -> date:
		"""Last day the month's KPI Templates can change: `freeze_day` of the following month."""
		following = getdate(add_months(self.start, 1))
		return following.replace(day=min(freeze_day, get_last_day(following).day))

	@property
	def label(self) -> str:
		return f"{self.month} {self.start.year}"


# Calendar quarters, whatever month the fiscal year starts in
QUARTERS = {
	"Q1": ("Jan", "Feb", "Mar"),
	"Q2": ("Apr", "May", "Jun"),
	"Q3": ("Jul", "Aug", "Sep"),
	"Q4": ("Oct", "Nov", "Dec"),
}


def quarter_of(month: str) -> str:
	return next(quarter for quarter, months in QUARTERS.items() if month in months)
