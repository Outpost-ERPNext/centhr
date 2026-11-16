# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from centhr.pms import kpi


class KPITemplate(Document):
	def autoname(self):
		self.name = kpi.make_name("KPI-T", self)

	def validate(self):
		kpi.set_employee_details(self)
		kpi.validate_one_per_month(self)
		self.validate_weights()
		kpi.check_not_frozen(self)

	def validate_weights(self):
		"""A row earns at most its weight and a month is scored out of 100, so more than 100 cannot be earned."""
		self.total_weight = sum(flt(row.weight) for row in self.items)
		if self.total_weight > 100:
			frappe.throw(
				_("The weights of the KPIs add up to {0}. They cannot be more than 100.").format(
					self.total_weight
				),
				title=_("Weight Limit Exceeded"),
			)

	def on_submit(self):
		# A migrated template gets its KPI Result from the CentHR site, in the KPI Result tab
		if not frappe.flags.centhr_migration:
			self.create_result()

	def create_result(self) -> str:
		"""The draft KPI Result the line manager fills in: the same KPIs, nothing achieved yet."""
		result = frappe.get_doc(
			{
				"doctype": kpi.RESULT,
				"fiscal_year": self.fiscal_year,
				"month": self.month,
				"employee": self.employee,
				"kpi_template": self.name,
				"items": [{field: row.get(field) for field in kpi.ITEM_FIELDS} for row in self.items],
			}
		)
		# HR submits templates; the result belongs to the line manager
		return result.insert(ignore_permissions=True).name

	def on_cancel(self):
		"""The results made from this template go with it: submitted ones are cancelled, drafts deleted."""
		if self.flags.cancelled_by_result:
			return
		for result in frappe.get_all(
			kpi.RESULT,
			filters={"kpi_template": self.name, "docstatus": ["!=", 2]},
			fields=["name", "docstatus"],
		):
			if result.docstatus == 0:
				frappe.delete_doc(kpi.RESULT, result.name, ignore_permissions=True)
				continue
			doc = frappe.get_doc(kpi.RESULT, result.name)
			doc.flags.cancelled_by_template = True
			doc.flags.ignore_permissions = True
			doc.cancel()
