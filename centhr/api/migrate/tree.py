# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.base import SAVEPOINT, Migrator
from centhr.api.migrate.client import MigrationError


class TreeMigrator(Migrator):
	"""Account and Cost Center: a tree whose names end with the company abbreviation.

	Parents must be migrated before their children, so the records are listed in tree order. A new
	company has its own chart of accounts and root cost center already, so those show as Already Exists.
	The parent link is mandatory, so map_links fails a record whose parent is not here yet.

	A root of the CentHR site that this site does not have is created under the local root of the same
	kind, since ERPNext does not take new roots.
	"""

	parent_field: str
	# Rows in tree order, so parents are migrated before their children
	order_by = "lft asc"
	# lft, rgt and old_parent are rebuilt here
	cleared_fields = ("lft", "rgt", "old_parent")

	def create(self, values: dict):
		if not values.get(self.parent_field):
			values[self.parent_field] = self.get_local_root()

		# The name is made from the company abbreviation of this site, which can differ on the CentHR site
		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values}).insert(ignore_permissions=True)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise

		if doc.name != self.remote["name"]:
			self.notes.append(_("Created as {0}").format(doc.name))
		return doc

	def get_local_root(self) -> str:
		filters = {"company": self.company, self.parent_field: ["is", "not set"], "is_group": 1}
		root = frappe.db.get_value(self.doctype, {**filters, **self.get_root_filters()}, "name")
		if not root:
			raise MigrationError(
				_("No root {0} of {1} on this site to create {2} under").format(
					_(self.doctype), self.company, self.remote["name"]
				)
			)
		self.notes.append(_("Root on the CentHR site, created under {0}").format(root))
		return root

	def get_root_filters(self) -> dict:
		return {}
