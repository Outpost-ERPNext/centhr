# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from hrms.payroll.utils import COMPONENT_PARENTFIELDS

from centhr.api.migrate.base import CHUNK_SIZE, LOGGER, SAVEPOINT, Migrator
from centhr.api.migrate.client import MigrationError


class SalaryStructureMigrator(Migrator):
	"""Its Salary Components must be migrated first.

	The user names each structure, and each company has its own CentHR site, so two companies can both
	have a "Standard" structure. The structure of a company is found through its CentHR API Logger entry
	or by name within the company (get_local_structures), never by name alone.
	"""

	doctype = "Salary Structure"
	list_fields = ("is_active", "payroll_frequency", "docstatus")
	# Matched through get_local_structures instead
	duplicate_fields = ()
	title_field = "name"

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		self.clear_double_payment_days(values)
		return values

	def clear_double_payment_days(self, values: dict) -> None:
		"""Older CentHR sites allow a formula row to depend on payment days even when its formula already
		uses a payment-days-based component. That reduces the amount twice and HRMS rejects the structure
		(see SalaryStructure.validate_payment_days_based_dependent_component), so clear the flag on such rows.
		"""
		rows = [row for table in COMPONENT_PARENTFIELDS for row in values.get(table) or []]
		abbreviations = [row["abbr"] for row in rows if row.get("depends_on_payment_days") and row.get("abbr")]
		for row in rows:
			formula = row.get("formula")
			if (
				formula
				and row.get("depends_on_payment_days")
				and any(re.search(r"\b" + re.escape(abbr) + r"\b", formula) for abbr in abbreviations)
			):
				row["depends_on_payment_days"] = 0
				message = _(
					"Depends On Payment Days cleared for {0}, its formula already uses a payment-days-based component"
				)
				self.notes.append(message.format(row.get("salary_component")))

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		return get_local_structures(self.company, [row["name"] for row in rows])

	def find_existing(self, values: dict) -> str | None:
		return get_local_structures(self.company, [self.remote["name"]]).get(self.remote["name"])

	def create(self, values: dict):
		name = self.remote["name"]
		if not frappe.db.exists(self.doctype, name):
			return super().create(values)

		# The name belongs to another company's structure here, so add the company abbreviation
		new_name = f"{name} - {frappe.get_cached_value('Company', self.company, 'abbr')}"
		if frappe.db.exists(self.doctype, new_name):
			raise MigrationError(
				_("{0} {1} already exists on this site as a different record").format(
					_(self.doctype), new_name
				)
			)

		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values})
			doc.insert(ignore_permissions=True, set_name=new_name)
			if self.remote.get("docstatus") == 1:
				doc.submit()
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise
		self.notes.append(
			_("{0} is taken by another company's structure, created as {1}").format(name, new_name)
		)
		return doc


class StructureMap:
	"""Salary Structure of the CentHR site -> the one of this company here, None if not migrated."""

	def __init__(self, company: str):
		self.company = company
		self.structures = {}

	def get_local(self, remote_structure: str | None) -> str | None:
		if not remote_structure:
			return None
		self.load([remote_structure])
		return self.structures[remote_structure]

	def get_local_or_throw(self, remote_structure: str) -> str:
		local = self.get_local(remote_structure)
		if not local:
			message = _(
				"Salary Structure {0} of {1} has not been migrated. Migrate it in the Salary Structure tab first."
			)
			raise MigrationError(message.format(remote_structure, self.company))
		return local

	def load(self, remote_structures: list[str]) -> None:
		missing = list({name for name in remote_structures if name and name not in self.structures})
		if missing:
			local = get_local_structures(self.company, missing)
			self.structures.update({name: local.get(name) for name in missing})


def get_local_structures(company: str, remote_structures: list[str]) -> dict[str, str]:
	"""Map Salary Structures of the company's CentHR site to the active structures of the company here."""
	created = {}
	for start in range(0, len(remote_structures), CHUNK_SIZE):
		for log in frappe.get_all(
			LOGGER,
			filters={
				"doctypes": "Salary Structure",
				"company": company,
				"status": "Success",
				"target_reference": ["is", "set"],
				"reference_name": ["in", remote_structures[start : start + CHUNK_SIZE]],
			},
			fields=["reference_name", "target_reference"],
			order_by="creation asc",
		):
			created[log.reference_name] = log.target_reference

	# Structures that were here already, or created by hand, keep the CentHR name within the company
	for name in set(remote_structures) - set(created):
		created[name] = name

	active = set(
		frappe.get_all(
			"Salary Structure",
			filters={"name": ["in", list(set(created.values()))], "company": company, "docstatus": ["!=", 2]},
			pluck="name",
		)
	)
	return {remote: local for remote, local in created.items() if local in active}


def migrate(company: str, name: str) -> frappe._dict:
	return SalaryStructureMigrator(company).migrate(name)
