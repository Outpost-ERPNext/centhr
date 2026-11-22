# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from functools import cached_property

import frappe
from frappe import _
from frappe.utils import flt

from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.kpi_template import KpiTemplateMigrator
from centhr.api.migrate.pms_base import PmsMigrator, find_local


class KpiResultMigrator(PmsMigrator):
	"""The company's PMS Settings must be migrated first. A result whose KPI Template is not here yet
	brings it along, so this tab alone migrates the templates and results of a whole fiscal year.
	The score is worked out again here from the achieved values; a note says so when it differs from
	the CentHR site's."""

	doctype = "KPI Result"
	list_fields = ("employee", "employee_name", "fiscal_year", "month", "overall_score", "docstatus")
	duplicate_fields = ("employee", "fiscal_year", "month")
	remote_filter_fields = ("fiscal_year", "month")
	# Found again by employee and month, see prepare
	cleared_fields = ("kpi_template",)

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		period = {key: values.get(key) for key in ("employee", "fiscal_year", "month")}
		values["kpi_template"] = find_local("KPI Template", **period) or self.migrate_template(remote, period)
		return values

	def migrate_template(self, remote: dict, period: dict) -> str:
		"""Migrate the result's KPI Template first, as the KPI Template tab does, with its own log."""
		name = remote.get("kpi_template") or self.find_remote_template(remote)
		if not name:
			raise MigrationError(
				_("{0} has no KPI Template for {1} {2}, here or on the CentHR site.").format(
					remote.get("employee_name") or remote.get("employee"),
					remote.get("month"),
					remote.get("fiscal_year"),
				)
			)
		result = self.templates.migrate(name)
		# The template's migration switched the flag off when it ended; this record is still migrating
		frappe.flags.centhr_migration = True
		template = find_local("KPI Template", **period)
		if result.status == "Failed" or not template:
			raise MigrationError(
				_("Its KPI Template {0} could not be migrated: {1}").format(
					name, result.error or _("it is for another employee or month")
				)
			)
		self.notes.append(_("KPI Template {0} migrated with it").format(template))
		return template

	def find_remote_template(self, remote: dict) -> str | None:
		"""Older results do not name their template; it is the employee's template of the month."""
		templates = self.client.get_all(
			"KPI Template",
			[
				["employee", "=", remote.get("employee")],
				["fiscal_year", "=", remote.get("fiscal_year")],
				["month", "=", remote.get("month")],
				["docstatus", "!=", 2],
			],
			["name"],
		)
		return templates[0]["name"] if templates else None

	@cached_property
	def templates(self) -> KpiTemplateMigrator:
		migrator = KpiTemplateMigrator(self.company)
		# One employee map for both, so each employee is looked up once
		migrator.employees = self.employees
		return migrator

	def after_create(self, doc) -> None:
		remote_score = flt(self.remote.get("overall_score"), 2)
		if abs(flt(doc.overall_score) - remote_score) > 0.01:
			self.notes.append(_("Score here is {0}, on CentHR {1}").format(doc.overall_score, remote_score))


def migrate(company: str, name: str) -> frappe._dict:
	return KpiResultMigrator(company).migrate(name)
