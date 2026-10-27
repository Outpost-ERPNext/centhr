# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.base import CHUNK_SIZE, LOGGER, SAVEPOINT, Migrator


class LeavePolicyMigrator(Migrator):
	"""Its Leave Types must be migrated first.

	Each company has its own CentHR site, and each site numbers its policies from HR-LPOL-.YYYY.-00001,
	so the same name is a different policy for each company. The policy created for a company is found
	through its CentHR API Logger entry (get_local_policies), never by name or title.
	"""

	doctype = "Leave Policy"
	list_fields = ("title", "docstatus")
	# Matched through the log instead, see get_local_policies
	duplicate_fields = ()
	title_field = "title"
	# Leave Policy has no company field
	filter_by_company = False

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		# Title is optional on older CentHR sites, but mandatory here
		values["title"] = values.get("title") or remote["name"]
		return values

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		return get_local_policies(self.company, [row["name"] for row in rows])

	def find_existing(self, values: dict) -> str | None:
		return get_local_policies(self.company, [self.remote["name"]]).get(self.remote["name"])

	def create(self, values: dict):
		name = self.remote["name"]
		if not frappe.db.exists(self.doctype, name):
			return super().create(values)

		# The name belongs to the policy of another company here, so take the next name of the series
		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values}).insert(ignore_permissions=True)
			if self.remote.get("docstatus") == 1:
				doc.submit()
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise
		self.notes.append(_("{0} is taken by another company's policy, created as {1}").format(name, doc.name))
		return doc

	def update_series(self, name: str) -> None:
		# Leave Policy is named by autoname (HR-LPOL-.YYYY.-.#####), not by a naming_series field
		self.remote.setdefault("naming_series", self.meta.autoname)
		super().update_series(name)


def get_local_policies(company: str, remote_policies: list[str]) -> dict[str, str]:
	"""Map Leave Policies of the company's CentHR site to the policies this tool created for them."""
	created = {}
	for start in range(0, len(remote_policies), CHUNK_SIZE):
		for log in frappe.get_all(
			LOGGER,
			filters={
				"doctypes": "Leave Policy",
				"company": company,
				"status": "Success",
				"target_reference": ["is", "set"],
				"reference_name": ["in", remote_policies[start : start + CHUNK_SIZE]],
			},
			fields=["reference_name", "target_reference"],
			order_by="creation asc",
		):
			created[log.reference_name] = log.target_reference

	if not created:
		return {}
	active = set(
		frappe.get_all(
			"Leave Policy",
			filters={"name": ["in", list(set(created.values()))], "docstatus": ["!=", 2]},
			pluck="name",
		)
	)
	return {remote: local for remote, local in created.items() if local in active}


def migrate(company: str, name: str) -> frappe._dict:
	return LeavePolicyMigrator(company).migrate(name)
