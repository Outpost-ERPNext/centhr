# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.pms_base import PmsMigrator, find_local, get_quarter


class Pms360DegreeMigrator(PmsMigrator):
	"""The 360 review of a quarter: its departments and the weight of each kind of reviewer. Only the
	company's own departments are kept, and only line manager and peer reviews, which are the ones given."""

	doctype = "PMS 360 Degree"
	list_fields = ("fiscal_year", "quarter", "month")
	duplicate_fields = ("company", "fiscal_year", "quarter")
	employee_fields = ()
	title_field = "name"
	remote_filter_fields = ("fiscal_year",)

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		existing = {}
		for row in rows:
			quarter = row.get("quarter") or ""
			local = find_local(
				self.doctype, company=self.company, fiscal_year=row.get("fiscal_year"), quarter=quarter
			)
			if quarter and local:
				existing[row["name"]] = local
		return existing

	def prepare(self, remote: dict) -> dict:
		departments = [row for row in map(self.make_department_row, remote.get("departments") or []) if row]
		if not departments:
			raise MigrationError(
				_("None of its departments is a department of {0} with a reviewer.").format(self.company)
			)
		return {
			"company": self.company,
			"fiscal_year": remote.get("fiscal_year"),
			"quarter": get_quarter(remote),
			"departments": departments,
		}

	def make_department_row(self, row: dict) -> dict | None:
		department = (
			self.get_local_link("Department", row.get("department")) if row.get("department") else None
		)
		if not department or frappe.db.get_value("Department", department, "company") != self.company:
			self.notes.append(
				_("Department {0} is not a department of {1} here, left out").format(
					row.get("department"), self.company
				)
			)
			return None
		# A kind of reviewer counts when it is ticked and has a weight
		weights = {
			kind: cint(row.get(f"{kind}_weight")) if cint(row.get(kind)) else 0
			for kind in ("superior", "peers")
		}
		if not any(weights.values()):
			self.notes.append(
				_("Department {0} has no line manager or peer weight, left out").format(department)
			)
			return None
		return {
			"department": department,
			"superior": int(bool(weights["superior"])),
			"superior_weight": weights["superior"],
			"peers": int(bool(weights["peers"])),
			"peers_weight": weights["peers"],
		}


def migrate(company: str, name: str) -> frappe._dict:
	return Pms360DegreeMigrator(company).migrate(name)
