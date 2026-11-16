# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from centhr.pms import peers
from centhr.pms.review import sync_peer_allocations

EMPLOYEE_FIELDS = ["company", "department", "designation", "grade", "reports_to", "status"]


class PMSEmployeeRelationship(Document):
	def validate(self):
		self.validate_not_locked()
		self.set_employee_details()
		self.validate_peers()
		self.peer_names = ", ".join(row.employee_name or row.employee for row in self.peers)

	def validate_not_locked(self):
		"""HR locks a mapping they have checked. Only locking and unlocking itself gets past the lock."""
		if self.is_new() or self.flags.changing_lock:
			return
		if frappe.db.get_value(self.doctype, self.name, "locked"):
			frappe.throw(_("This mapping is locked. Unlock it to change it."), title=_("Locked"))

	def set_employee_details(self):
		"""The mapping follows the Employee record, so a transfer or a new manager shows here on the next save."""
		employee = frappe.db.get_value("Employee", self.employee, EMPLOYEE_FIELDS, as_dict=True)
		self.company = employee.company
		self.department = employee.department
		self.designation = employee.designation
		self.grade = employee.grade
		self.line_manager = employee.reports_to

	def validate_peers(self):
		chosen = [row.employee for row in self.peers]
		if len(chosen) != len(set(chosen)):
			frappe.throw(_("The same peer is listed twice."))
		if len(chosen) > peers.MAX_PEERS:
			frappe.throw(_("An employee has at most {0} peers.").format(peers.MAX_PEERS))
		if self.employee in chosen:
			frappe.throw(_("An employee cannot be their own peer."))
		if self.line_manager and self.line_manager in chosen:
			frappe.throw(_("The line manager reviews this employee already, so they cannot also be a peer."))

		for row in self.peers:
			peer = frappe.db.get_value("Employee", row.employee, ["company", "status"], as_dict=True)
			if peer.status != "Active":
				frappe.throw(_("Peer {0} is not an active employee.").format(row.employee))
			if peer.company != self.company:
				frappe.throw(
					_("Peer {0} works for {1}, not {2}.").format(row.employee, peer.company, self.company)
				)

	def on_update(self):
		# The peer mapping run decides each employee's peers itself
		if not self.flags.skip_reverse_mapping:
			peers.add_reverse_mappings(self)
		if not frappe.flags.centhr_migration:
			sync_peer_allocations(self)

	def set_lock(self, locked: bool) -> None:
		self.locked = int(locked)
		self.flags.changing_lock = self.flags.skip_reverse_mapping = True
		try:
			self.save()
		finally:
			# A later save of this same document is an ordinary edit again
			self.flags.changing_lock = self.flags.skip_reverse_mapping = False
