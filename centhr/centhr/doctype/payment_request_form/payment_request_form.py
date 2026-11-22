# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

# Who decides on a payment request. The requester works in HR; the money is Accounts' to release
APPROVER_ROLES = ("Accounts Manager", "System Manager")
PENDING, APPROVED, REJECTED, PAID = "Pending Approval", "Approved", "Rejected", "Paid"
SUBJECT_FIELD = {"Payroll": "payroll_entry", "Statutory": "statutory_obligation"}


class PaymentRequestForm(Document):
	def before_insert(self):
		self.status = PENDING
		self.requested_by = frappe.session.user
		self.approved_by = self.approved_on = self.rejection_reason = self.journal_entry = None

	def validate(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("A payment request needs an amount above zero."))
		subject = SUBJECT_FIELD[self.request_type]
		if not self.get(subject):
			frappe.throw(_("Choose the {0} this request pays.").format(self.meta.get_label(subject)))
		self.currency = frappe.get_cached_value("Company", self.company, "default_currency")
		if self.is_new():
			self.validate_no_open_request(subject)

	def validate_no_open_request(self, subject: str):
		"""One request at a time per payroll entry or obligation; a rejected one can be followed by a new one.
		A paid request ends a payroll entry for good, while an obligation is paid again each period."""
		closed = [REJECTED] if self.request_type == "Payroll" else [REJECTED, PAID]
		existing = frappe.db.get_value(
			self.doctype, {subject: self.get(subject), "status": ["not in", closed]}, ["name", "status"]
		)
		if existing:
			frappe.throw(
				_("Payment request {0} for {1} is {2} already.").format(
					existing[0], self.get(subject), _(existing[1]).lower()
				),
				title=_("Request Exists"),
			)

	@frappe.whitelist(methods=["POST"])
	def approve(self):
		self.decide(APPROVED)

	@frappe.whitelist(methods=["POST"])
	def reject(self, reason: str | None = None):
		reason = (reason or "").strip()
		if not reason:
			frappe.throw(_("Say why this payment request is rejected."), title=_("Reason Missing"))
		self.rejection_reason = reason
		self.decide(REJECTED)

	def decide(self, status: str):
		frappe.only_for(APPROVER_ROLES)
		if self.status != PENDING:
			frappe.throw(_("This payment request is {0} already.").format(_(self.status).lower()))
		self.status = status
		self.approved_by = frappe.session.user
		self.approved_on = now_datetime()
		self.save(ignore_permissions=True)

	def set_bank_entry(self, journal_entry: str | None):
		"""The entry that pays the request. A submitted one makes it Paid."""
		submitted = journal_entry and frappe.db.get_value("Journal Entry", journal_entry, "docstatus") == 1
		self.db_set({"journal_entry": journal_entry, "status": PAID if submitted else APPROVED})


def follow_bank_entry(doc, method=None):
	"""Journal Entry on_submit, on_cancel and on_trash: a request is Paid once its bank entry is
	submitted, and waits for a new bank entry when that one is cancelled or deleted."""
	for name in frappe.get_all(
		"Payment Request Form",
		filters={"journal_entry": doc.name, "status": ["in", [APPROVED, PAID]]},
		pluck="name",
	):
		frappe.get_doc("Payment Request Form", name).set_bank_entry(
			doc.name if method == "on_submit" else None
		)
