# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Finds the entity-site name of a record that a synced document links to.

An entity site can have its own chart, with another company abbreviation, so Accounts and Cost Centers
are matched by name, then by the name with the entity site's abbreviation, then by account_name or
cost_center_name within the company. Departments are matched by department_name and company. Synced
documents (an advance that a claim or a payment uses) are found from their logged POST or migration.
"""

import frappe
from frappe import _

# Account and Cost Center names are made from this field, the number and the company abbreviation
NAME_FIELDS = {"Account": "account_name", "Cost Center": "cost_center_name"}
SYNCED_DOCTYPES = ("Employee Advance", "Expense Claim", "Payment Entry")


class RemoteLinks:
	"""Local name → entity-site name for one sync to one target. Results are cached for the job."""

	def __init__(self, sync):
		# sync: the RecordSync of the document, for its client and its synced-name lookups
		self.sync = sync
		self.client = sync.client
		self.company = sync.client.target.company
		self.cache = {}
		self._remote_abbr = None

	def get(self, doctype: str, name: str | None) -> str | None:
		if not name or not doctype:
			return name

		key = (doctype, name)
		if key not in self.cache:
			self.cache[key] = self.find(doctype, name)
		return self.cache[key]

	def find(self, doctype: str, name: str) -> str:
		if doctype in NAME_FIELDS:
			return self.find_tree_record(doctype, name)
		if doctype == "Department":
			return self.find_department(name)
		if doctype == "Employee":
			return self.sync.get_remote_employee(name)
		if doctype in SYNCED_DOCTYPES:
			return self.find_synced(doctype, name)
		# Masters such as Channel, Expense Claim Type and Mode of Payment have the same name everywhere
		return name

	def find_tree_record(self, doctype: str, name: str) -> str:
		candidates = [name]
		local_abbr = frappe.get_cached_value("Company", self.company, "abbr")
		suffix = f" - {local_abbr}"
		if self.remote_abbr and self.remote_abbr != local_abbr and name.endswith(suffix):
			candidates.append(f"{name.removesuffix(suffix)} - {self.remote_abbr}")

		data = self.client.get_list(doctype, [["name", "in", candidates]], ["name"], limit=len(candidates))
		found = {row["name"] for row in data or ()}
		for candidate in candidates:
			if candidate in found:
				return candidate

		name_field = NAME_FIELDS[doctype]
		title = frappe.db.get_value(doctype, name, name_field)
		if title:
			data = self.client.get_list(
				doctype, [[name_field, "=", title], ["company", "=", self.company]], ["name"]
			)
			if data:
				return data[0]["name"]

		self.client.fail(_("{0} {1} does not exist in the target system").format(_(doctype), name))

	def find_department(self, name: str) -> str:
		from centhr.api.department import to_filters

		values = frappe.db.get_value("Department", name, ["department_name", "company"], as_dict=True)
		# A department without a company, like "All Departments", has the same name everywhere
		if not values or not values.company:
			return name

		data = self.client.get_list("Department", to_filters(values), ["name"])
		if not data:
			self.client.fail(_("Department {0} does not exist in the target system").format(name))
		return data[0]["name"]

	def find_synced(self, doctype: str, name: str) -> str:
		remote_name = self.sync.get_synced_name(name, doctype)
		if not remote_name:
			self.client.fail(
				_("{0} {1} is not in the target system yet. Sync it first").format(_(doctype), name)
			)
		return remote_name

	@property
	def remote_abbr(self) -> str:
		"""Abbreviation of the company on the entity site."""
		if self._remote_abbr is None:
			data = self.client.get_list("Company", [["name", "=", self.company]], ["abbr"])
			self._remote_abbr = (data[0].get("abbr") if data else "") or ""
		return self._remote_abbr
