# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""IOU Advance Report (SOP: Advance Report): total paid as IOU, claimed against it, and the balance left."""

import frappe
from frappe import _

from centhr.iou.advance import outstanding


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	currency = {"fieldtype": "Currency", "options": "currency", "width": 120}
	return [
		{"label": _("IOU"), "fieldname": "name", "fieldtype": "Link", "options": "Employee Advance", "width": 150},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 140},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Purpose"), "fieldname": "purpose", "fieldtype": "Data", "width": 180},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", **currency},
		{"label": _("Claimed Amount"), "fieldname": "claimed_amount", **currency},
		{"label": _("Returned / Deducted"), "fieldname": "return_amount", **currency},
		{"label": _("Balance"), "fieldname": "balance", **currency},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]


def get_data(filters):
	conditions = {"docstatus": 1}
	for field in ("company", "employee", "department", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ["between", [filters.from_date, filters.to_date]]

	rows = frappe.get_list(
		"Employee Advance",
		filters=conditions,
		fields=[
			"name", "employee", "employee_name", "department", "posting_date", "purpose", "status", "due_date",
			"paid_amount", "claimed_amount", "return_amount", "currency",
		],
		order_by="posting_date desc",
		limit_page_length=0,
	)
	for row in rows:
		row.balance = outstanding(row)
	if filters.get("outstanding_only"):
		rows = [row for row in rows if row.balance > 0]
	return rows
