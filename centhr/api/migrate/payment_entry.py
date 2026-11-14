# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.base import Migrator
from centhr.api.migrate.client import MigrationError

SAVEPOINT = "centhr_payment_entry"


class PaymentEntryMigrator(Migrator):
	"""The party, the Accounts and the referenced documents must be migrated first.

	Migrate an Employee Advance before the Payment Entry that pays it, and that Payment Entry before an
	Expense Claim that uses the advance. Migrate the Payment Entry that reimburses a claim after the claim.
	A submitted Payment Entry is submitted here too, which books its ledger entries and updates the paid
	amounts of the referenced documents on this site.
	"""

	doctype = "Payment Entry"
	list_fields = (
		"posting_date",
		"payment_type",
		"party_type",
		"party",
		"party_name",
		"paid_amount",
		"mode_of_payment",
		"reference_no",
		"status",
		"docstatus",
	)
	# The party comes first, because it narrows the lookup of local records the most
	duplicate_fields = ("party", "party_type", "payment_type", "posting_date", "paid_amount")
	title_field = "party_name"

	# Fetch

	def get_remote_filters(self, filters: frappe._dict) -> list | None:
		employee = filters.pop("employee", None)
		remote = super().get_remote_filters(filters)
		if not employee:
			return remote

		remote_employee = self.employees.get_remote(employee)
		if not remote_employee:
			return None
		return [*remote, ["party_type", "=", "Employee"], ["party", "=", remote_employee]]

	def get_section_filters(self, filters: frappe._dict) -> list:
		remote = []
		if filters.from_date:
			remote.append(["posting_date", ">=", filters.from_date])
		if filters.to_date:
			remote.append(["posting_date", "<=", filters.to_date])
		for fieldname in ("payment_type", "party_type"):
			value = filters.get(fieldname)
			if value and value != "All":
				remote.append([fieldname, "=", value])
		return remote

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		self.employees.load([row.get("party") for row in rows if row.get("party_type") == "Employee"])
		return super().get_existing_names(rows)

	def get_key(self, row: dict) -> tuple | None:
		party = self.get_local_party(row.get("party_type"), row.get("party"))
		if not party:
			return None
		return super().get_key({**row, "party": party})

	# Migrate

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		if values.get("party_type") and values.get("party"):
			values["party"] = self.get_party(values["party_type"], values["party"])
		for row in values.get("references") or []:
			self.check_reference(row)
		return values

	def get_local_party(self, party_type: str | None, party: str | None) -> str | None:
		if not party_type or not party:
			return None
		if party_type == "Employee":
			return self.employees.get_local(party)
		return frappe.db.get_value(party_type, party, "name")

	def get_party(self, party_type: str, party: str) -> str:
		local = self.get_local_party(party_type, party)
		if not local:
			raise MigrationError(
				_("{0} {1} does not exist on this site. Migrate or create it first.").format(
					_(party_type), party
				)
			)
		return local

	def check_reference(self, row: dict) -> None:
		"""Every migrator keeps the CentHR name, so the referenced document has the same name here."""
		reference_doctype, reference_name = row.get("reference_doctype"), row.get("reference_name")
		if reference_doctype and reference_name and not frappe.db.exists(reference_doctype, reference_name):
			raise MigrationError(
				_("{0} {1} does not exist on this site. Migrate or create it first.").format(
					_(reference_doctype), reference_name
				)
			)

	def create(self, values: dict):
		muted = frappe.flags.mute_emails
		frappe.flags.mute_emails = True
		# A failed payment must not leave the advances with the reset paid amount
		frappe.db.savepoint(SAVEPOINT)
		try:
			if self.remote.get("docstatus") == 1:
				self.reset_advances_paid(values)
			return super().create(values)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise
		finally:
			frappe.flags.mute_emails = muted

	def reset_advances_paid(self, values: dict) -> None:
		"""Set the paid amount of each advance from this site's ledger.

		The Employee Advance migrator copies the paid amount of the CentHR site. Payment Entry takes
		advance_amount - paid_amount as the outstanding amount, so the copied value would block the
		payment. After the submit, HRMS sets the paid amount from the new ledger entries.
		"""
		for row in values.get("references") or []:
			if row.get("reference_doctype") == "Employee Advance":
				frappe.get_doc("Employee Advance", row["reference_name"]).set_total_advance_paid()


def migrate(company: str, name: str) -> frappe._dict:
	return PaymentEntryMigrator(company).migrate(name)
