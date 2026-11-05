# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

QUARTER_MONTHS = [1, 4, 7, 10]


class StatutoryObligation(Document):
	def validate(self):
		self.validate_accounts()
		self.due_month_list()

	def validate_accounts(self):
		for field, label in (("liability_account", _("Liability Account")), ("payment_account", _("Payment Account"))):
			account = self.get(field)
			if account and frappe.db.get_value("Account", account, "company") != self.company:
				frappe.throw(_("{0} {1} does not belong to company {2}.").format(label, account, self.company))
		# A payment request debits it without a party, which ERPNext refuses for party accounts
		if frappe.db.get_value("Account", self.liability_account, "account_type") in ("Payable", "Receivable"):
			frappe.throw(
				_("{0} is a party account. Use a plain liability account, such as the pension or tax payable account.").format(
					self.liability_account
				)
			)

	def due_month_list(self) -> list[int]:
		"""The months it falls due; empty for monthly obligations."""
		if self.frequency == "Monthly":
			return []
		try:
			months = sorted({int(m) for m in (self.due_months or "").replace(" ", "").split(",") if m})
		except ValueError:
			frappe.throw(_("Due Months must be month numbers separated by commas, e.g. 3,12."))
		if not months and self.frequency == "Quarterly":
			return QUARTER_MONTHS
		if not months or any(m < 1 or m > 12 for m in months):
			frappe.throw(_("Set the months {0} falls due, e.g. 3,12.").format(self.obligation_name))
		return months
