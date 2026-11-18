# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.pms_base import PmsMigrator, find_local


class KpiResultMigrator(PmsMigrator):
	"""Its KPI Template and the company's PMS Settings must be migrated first. The score is worked out
	again here from the achieved values; a note says so when it differs from the CentHR site's."""

	doctype = "KPI Result"
	list_fields = ("employee", "employee_name", "fiscal_year", "month", "overall_score", "docstatus")
	duplicate_fields = ("employee", "fiscal_year", "month")
	remote_filter_fields = ("fiscal_year", "month")
	# Found again by employee and month, see prepare
	cleared_fields = ("kpi_template",)

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		period = {key: values.get(key) for key in ("employee", "fiscal_year", "month")}
		values["kpi_template"] = find_local("KPI Template", **period)
		if not values["kpi_template"]:
			raise MigrationError(
				_(
					"{0} has no KPI Template for {1} {2} here. Migrate it in the KPI Template tab first."
				).format(
					remote.get("employee_name") or remote.get("employee"),
					remote.get("month"),
					remote.get("fiscal_year"),
				)
			)
		return values

	def after_create(self, doc) -> None:
		remote_score = flt(self.remote.get("overall_score"), 2)
		if abs(flt(doc.overall_score) - remote_score) > 0.01:
			self.notes.append(_("Score here is {0}, on CentHR {1}").format(doc.overall_score, remote_score))


def migrate(company: str, name: str) -> frappe._dict:
	return KpiResultMigrator(company).migrate(name)
