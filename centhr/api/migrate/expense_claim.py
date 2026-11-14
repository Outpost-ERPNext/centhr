# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from centhr.api.migrate.base import Migrator
from centhr.api.migrate.client import MigrationError


class ExpenseClaimMigrator(Migrator):
	"""The Employee, the Accounts, the Cost Centers and the linked Employee Advances must be migrated first.

	A submitted claim is submitted here too, which books its ledger entries on this site. HRMS then sets
	the reimbursed amount from this site's ledger, so a claim paid on CentHR shows as unpaid here until
	its Payment Entry is migrated in the Payment Entry tab.
	"""

	doctype = "Expense Claim"
	list_fields = (
		"employee",
		"employee_name",
		"posting_date",
		"total_claimed_amount",
		"total_sanctioned_amount",
		"approval_status",
		"status",
		"docstatus",
	)
	duplicate_fields = ("employee", "posting_date", "total_claimed_amount")
	# Vehicle Logs and Delivery Trips are not migrated
	# A new record must start in the first workflow state; submitting it sets "Approved".
	cleared_fields = ("vehicle_log", "delivery_trip", "workflow_state")

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = []
		if filters.from_date:
			remote.append(["posting_date", ">=", filters.from_date])
		if filters.to_date:
			remote.append(["posting_date", "<=", filters.to_date])
		if filters.status and filters.status != "All":
			remote.append(["status", "=", filters.status])
		return remote

	copied_masters = ("Expense Claim Type",)

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		if remote.get("docstatus") == 1 and values.get("approval_status") not in ("Approved", "Rejected"):
			# Older CentHR sites submitted claims without setting the status; this HRMS refuses that
			self.notes.append(
				_("Approval Status was {0} on CentHR; submitted claims are Approved here").format(
					values.get("approval_status") or _("empty")
				)
			)
			values["approval_status"] = "Approved"
		for row in values.get("advances") or []:
			self.check_advance_payment(row)
		return values

	def check_advance_payment(self, row: dict) -> None:
		"""The claim books against the payment of the advance, so that payment must exist here."""
		if not flt(row.get("allocated_amount")):
			return

		reference_type, reference_name = row.get("reference_type"), row.get("reference_name")
		if reference_type and reference_name and not frappe.db.exists(reference_type, reference_name):
			raise MigrationError(
				_("{0} {1} that paid Employee Advance {2} does not exist on this site. Migrate it first.").format(
					_(reference_type), reference_name, row.get("employee_advance")
				)
			)

	def find_existing(self, values: dict) -> str | None:
		"""Employees sometimes submit the same claim many times; a submitted claim never matches a draft copy."""
		filters = {fieldname: values.get(fieldname) for fieldname in self.duplicate_fields}
		filters["docstatus"] = self.remote.get("docstatus") or 0
		return frappe.db.get_value(self.doctype, filters, "name")

	def create(self, values: dict):
		# CentHR notified the approver and the employee already
		muted = frappe.flags.mute_emails
		frappe.flags.mute_emails = True
		try:
			doc = super().create(values)
		finally:
			frappe.flags.mute_emails = muted

		if doc.docstatus == 1 and flt(self.remote.get("total_amount_reimbursed")) != flt(
			doc.total_amount_reimbursed
		):
			self.notes.append(
				_("Status here is {0}, on CentHR {1}. Migrate the reimbursement Payment Entry to match.").format(
					_(doc.status), _(self.remote.get("status"))
				)
			)
		return doc


def migrate(company: str, name: str) -> frappe._dict:
	return ExpenseClaimMigrator(company).migrate(name)
