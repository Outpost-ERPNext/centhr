# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from centhr.pms.scoring import Band

BAND_TABLES = ("kpi_score", "overall_score", "increments")


class PMSSettings(Document):
	def validate(self):
		self.validate_weights()
		self.validate_bands()
		self.validate_increments()
		self.validate_grade_levels()

	def validate_weights(self):
		"""The overall score is KPI average x KPI weight + 360 score x 360 weight, so they share 100%."""
		kpi, review = flt(self.overall_kpi_weight), flt(self.overall__360_weight)
		if kpi < 0 or review < 0:
			frappe.throw(_("Weights cannot be negative."))
		if (kpi or review) and kpi + review != 100:
			frappe.throw(
				_("Overall KPI Weight and Overall 360 Weight must add up to 100. They add up to {0}.").format(
					kpi + review
				)
			)

	def validate_bands(self):
		for table in BAND_TABLES:
			for row in self.get(table):
				Band.parse(row.score)

	def validate_increments(self):
		for row in self.increments:
			if row.status == "Increment" and not is_number(row.increment_):
				frappe.throw(
					_("Row {0} of Increments: set Increment % to a number, such as 10.").format(row.idx)
				)

	def validate_grade_levels(self):
		grades = [row.grade for row in self.grade_levels]
		if len(grades) != len(set(grades)):
			frappe.throw(_("Grade Levels lists the same grade twice."))


def get_settings(company: str) -> PMSSettings:
	"""The PMS policy of a company. Scoring reads it for every employee, whoever is logged in."""
	if not frappe.db.exists("PMS Settings", company):
		frappe.throw(
			_("Company {0} has no PMS Settings. Ask HR to create them.").format(frappe.bold(company)),
			title=_("Missing PMS Settings"),
		)
	return frappe.get_cached_doc("PMS Settings", company)


def is_number(value: str | None) -> bool:
	try:
		float((value or "").replace("%", "").strip())
	except ValueError:
		return False
	return True
