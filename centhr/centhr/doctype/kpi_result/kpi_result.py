# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from centhr.centhr.doctype.pms_settings.pms_settings import get_settings
from centhr.pms import kpi
from centhr.pms.scoring import kpi_remark, score_kpi_result


class KPIResult(Document):
	def autoname(self):
		self.name = kpi.make_name("KPI-R", self)

	def validate(self):
		kpi.set_employee_details(self)
		kpi.validate_one_per_month(self)
		# Results migrated from the CentHR site are kept as they were scored there
		if not frappe.flags.centhr_migration:
			self.copy_kpis_from_template()
		self.calculate_scores()

	def copy_kpis_from_template(self):
		"""The template decides the KPIs, targets and weights. Only the achieved values belong to the
		result, so whatever the form sent for the rest is replaced."""
		if not self.kpi_template:
			frappe.throw(_("A KPI Result is created by submitting a KPI Template, not by hand."))

		template = frappe.get_doc(kpi.TEMPLATE, self.kpi_template)
		if template.employee != self.employee or len(template.items) != len(self.items):
			frappe.throw(
				_("The KPIs of this result do not match KPI Template {0}.").format(self.kpi_template),
				title=_("KPIs Changed"),
			)
		for row, source in zip(self.items, template.items, strict=True):
			for field in kpi.ITEM_FIELDS:
				row.set(field, source.get(field))

	def calculate_scores(self):
		self.overall_score = score_kpi_result(self.items)
		self.remark = kpi_remark(self.overall_score, get_settings(self.company).kpi_score)

	def before_submit(self):
		self.validate_achieved()
		self.validate_template_not_cancelled()

	def validate_achieved(self):
		"""0 achieved is most often a row the manager skipped. Where lower is better it is a real value."""
		for row in self.items:
			negative = (row.polarity or "").lower() == "negative"
			if not row.not_measured and not negative and not flt(row.achieved):
				frappe.throw(
					_(
						"Row {0}: enter what was achieved for {1}, or tick Not Measured / N/A if there is nothing to report."
					).format(row.idx, frappe.bold(row.kpi)),
					title=_("Achieved Missing"),
				)

	def validate_template_not_cancelled(self):
		if self.kpi_template and frappe.db.get_value(kpi.TEMPLATE, self.kpi_template, "docstatus") == 2:
			frappe.throw(
				_("KPI Template {0} is cancelled, so this KPI Result cannot be submitted.").format(
					self.kpi_template
				)
			)

	def on_cancel(self):
		"""A cancelled result reopens the month: its template is cancelled too, to be amended and
		submitted again."""
		if self.flags.cancelled_by_template or not self.kpi_template:
			return
		template = frappe.get_doc(kpi.TEMPLATE, self.kpi_template)
		if template.docstatus == 1:
			template.flags.cancelled_by_result = True
			template.flags.ignore_permissions = True
			template.cancel()
