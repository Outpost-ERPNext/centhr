# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.pms_base import PmsMigrator
from centhr.pms.peers import MAX_PEERS


class PmsEmployeeRelationshipMigrator(PmsMigrator):
	"""An employee's peer mapping. The department, grade and line manager come from the Employee
	record here. A peer is kept when they are on this site, active and of the same company."""

	doctype = "PMS Employee Relationship"
	list_fields = ("employee", "employee_name", "department", "line_manager_name", "is_locked")
	duplicate_fields = ("employee",)

	def prepare(self, remote: dict) -> dict:
		employee = self.local_employee(remote.get("employee"), _("Employee"))
		return {
			"employee": employee,
			"peers": [{"employee": peer} for peer in self.get_peers(employee, remote)],
			# "is_locked" on the CentHR site
			"locked": remote.get("is_locked") or 0,
		}

	def get_peers(self, employee: str, remote: dict) -> list[str]:
		company = frappe.db.get_value("Employee", employee, "company")
		peers = []
		for row in remote.get("peers") or []:
			peer = self.employees.get_local(row.get("employee")) if row.get("employee") else None
			details = (
				frappe.db.get_value("Employee", peer, ["status", "company"], as_dict=True) if peer else None
			)
			if not details or details.status != "Active" or details.company != company or peer == employee:
				self.notes.append(
					_("Peer {0} is not an active employee of {1} here, left out").format(
						row.get("employee"), company
					)
				)
			elif peer not in peers:
				peers.append(peer)
		if len(peers) > MAX_PEERS:
			self.notes.append(_("Only the first {0} peers are kept").format(MAX_PEERS))
		return peers[:MAX_PEERS]

	def before_insert(self, doc) -> None:
		# Each employee's own mapping is migrated; nothing is mirrored onto the peers
		doc.flags.skip_reverse_mapping = True


def migrate(company: str, name: str) -> frappe._dict:
	return PmsEmployeeRelationshipMigrator(company).migrate(name)
