# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class PayrollMasterSheet(Document):
	"""One pay cycle's master sheet; centhr.payroll_dashboard.master_sheet stores and reads it."""
