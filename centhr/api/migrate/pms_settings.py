# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.pms_base import PmsMigrator

COPIED_FIELDS = ("overall_kpi_weight", "overall__360_weight", "kpi_score", "overall_score", "increments")


class PmsSettingsMigrator(PmsMigrator):
	"""The CentHR site has one PMS Settings for the whole site. Here it becomes the settings of the
	company the tool is run for. The company logo is a file on the CentHR site and is not copied."""

	doctype = "PMS Settings"
	list_fields = ("overall_kpi_weight", "overall__360_weight")
	duplicate_fields = ("company",)
	employee_fields = ()
	title_field = "name"

	def fetch(self, filters: dict) -> list[dict]:
		remote = self.client.get_doc(self.doctype, self.doctype)
		rows = [{"name": self.doctype, **{field: remote.get(field) for field in self.list_fields}}]
		self.set_status(rows)
		return rows

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		return {self.doctype: self.company} if frappe.db.exists(self.doctype, self.company) else {}

	def prepare(self, remote: dict) -> dict:
		values = {field: remote.get(field) for field in COPIED_FIELDS}
		for table in ("kpi_score", "overall_score", "increments"):
			child_meta = frappe.get_meta(self.meta.get_field(table).options)
			values[table] = [self.strip(row, child_meta) for row in values[table] or []]
		values["company"] = self.company
		values["pms__channel"] = self.get_channel_rows(remote)
		return values

	def get_channel_rows(self, remote: dict) -> list[dict]:
		"""HRBP per channel, for the channels and employees that are on this site."""
		rows = []
		for row in remote.get("pms__channel") or []:
			channel = frappe.db.get_value("Channel", row.get("channel"), "name")
			if not channel:
				self.notes.append(
					_("Channel {0} not found, its HRBP row left out").format(row.get("channel"))
				)
				continue
			hrbp = self.employees.get_local(row.get("hrbps")) if row.get("hrbps") else None
			rows.append({"channel": channel, "hrbps": hrbp})
		return rows

	def find_existing(self, values: dict) -> str | None:
		return frappe.db.exists(self.doctype, self.company)


def migrate(company: str, name: str) -> frappe._dict:
	return PmsSettingsMigrator(company).migrate(name)
