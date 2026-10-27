# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.client import TargetClient

LOGGER = "CentHR API Logger"
# Account and Cost Center names are made from this field, the number and the company abbreviation
NAME_FIELDS = {"Account": "account_name", "Cost Center": "cost_center_name"}


class TreeMap:
	"""Match Accounts and Cost Centers of the CentHR site to records of this site.

	The CentHR site can have its own chart, with other numbers or another company abbreviation, so the
	name alone does not always match. The last match is by account_name or cost_center_name within the
	company, the same key that finds duplicates.
	"""

	def __init__(self, client: TargetClient, company: str):
		self.client = client
		self.company = company
		self.local_by_remote = {}
		self._remote_abbr = None

	def get_local(self, doctype: str, remote_name: str) -> str | None:
		key = (doctype, remote_name)
		if key not in self.local_by_remote:
			self.local_by_remote[key] = (
				frappe.db.get_value(doctype, remote_name, "name")
				or self.get_by_local_abbr(doctype, remote_name)
				or self.get_created(doctype, remote_name)
				or self.get_by_title(doctype, remote_name)
			)
		return self.local_by_remote[key]

	def get_by_local_abbr(self, doctype: str, remote_name: str) -> str | None:
		suffix = f" - {self.remote_abbr}"
		if not self.remote_abbr or not remote_name.endswith(suffix):
			return None
		local_abbr = frappe.get_cached_value("Company", self.company, "abbr")
		return frappe.db.get_value(doctype, f"{remote_name.removesuffix(suffix)} - {local_abbr}", "name")

	def get_created(self, doctype: str, remote_name: str) -> str | None:
		"""The record that this tool created, which can have a different name here."""
		created = frappe.get_all(
			LOGGER,
			filters={
				"doctypes": doctype,
				"company": self.company,
				"status": "Success",
				"reference_name": remote_name,
				"target_reference": ["is", "set"],
			},
			pluck="target_reference",
			order_by="creation desc",
			limit=1,
		)
		return frappe.db.get_value(doctype, created[0], "name") if created else None

	def get_by_title(self, doctype: str, remote_name: str) -> str | None:
		name_field = NAME_FIELDS[doctype]
		rows = self.client.get_all(doctype, [["name", "=", remote_name]], [name_field])
		if not rows or not rows[0].get(name_field):
			return None
		return frappe.db.get_value(doctype, {name_field: rows[0][name_field], "company": self.company}, "name")

	@property
	def remote_abbr(self) -> str | None:
		"""Abbreviation of the company on the CentHR site."""
		if self._remote_abbr is None:
			rows = self.client.get_all("Company", [["name", "=", self.company]], ["abbr"])
			self._remote_abbr = rows[0].get("abbr") if rows else ""
		return self._remote_abbr
