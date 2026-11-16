# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PMS360Degree(Document):
	def autoname(self):
		abbr = frappe.get_cached_value("Company", self.company, "abbr")
		self.name = f"PMS 360-{abbr}-{self.fiscal_year}-{self.quarter}"

	def validate(self):
		self.validate_one_per_quarter()
		self.validate_departments()

	def validate_one_per_quarter(self):
		filters = {"company": self.company, "fiscal_year": self.fiscal_year, "quarter": self.quarter}
		existing = frappe.db.get_value(self.doctype, {**filters, "name": ["!=", self.name]}, "name")
		if existing:
			frappe.throw(
				_("{0} already has a 360 review for {1} {2}: {3}").format(
					self.company, self.quarter, self.fiscal_year, existing
				),
				title=_("Already Exists"),
			)

	def validate_departments(self):
		seen = set()
		for row in self.departments:
			if row.department in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, row.department))
			seen.add(row.department)
			if frappe.db.get_value("Department", row.department, "company") != self.company:
				frappe.throw(
					_("Row {0}: {1} is not a department of {2}.").format(
						row.idx, row.department, self.company
					)
				)
			self.validate_weights(row)

	def validate_weights(self, row):
		if not row.superior and not row.peers:
			frappe.throw(_("Row {0}: choose who reviews {1}.").format(row.idx, row.department))
		for enabled, weight, label in (
			(row.superior, row.superior_weight, _("Line Manager Weight")),
			(row.peers, row.peers_weight, _("Peer Weight")),
		):
			if enabled and not 0 < (weight or 0) <= 100:
				frappe.throw(_("Row {0}: {1} must be between 1 and 100.").format(row.idx, label))


def get_department_review(company: str, department: str, fiscal_year: str, quarter: str):
	"""Who reviews a department's employees in a quarter and with what weights. None when the
	department is not part of that quarter's 360 review."""
	parent = frappe.db.get_value(
		"PMS 360 Degree", {"company": company, "fiscal_year": fiscal_year, "quarter": quarter}, "name"
	)
	if not parent:
		return None
	rows = frappe.get_all(
		"PMS 360 Degree Departments",
		filters={"parent": parent, "department": department},
		fields=["department", "superior", "superior_weight", "peers", "peers_weight"],
	)
	return rows[0] if rows else None
