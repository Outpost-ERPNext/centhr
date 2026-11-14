# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""IOU Advance Summary (SOP: Advance Summary Report): outstanding IOUs in aging buckets past the due date."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

from centhr.iou.advance import outstanding

# (days past due up to, fieldname, label)
BUCKETS = (
	(0, "not_due", "Not Due"),
	(30, "overdue_0_30", "1-30 Days"),
	(60, "overdue_31_60", "31-60 Days"),
	(90, "overdue_61_90", "61-90 Days"),
	(None, "overdue_90_plus", "90+ Days"),
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	columns = [
		{"label": _("IOU"), "fieldname": "name", "fieldtype": "Link", "options": "Employee Advance", "width": 150},
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 140},
		{"label": _("Purpose Type"), "fieldname": "purpose_type", "fieldtype": "Data", "width": 100},
		{"label": _("Payment Date"), "fieldname": "payment_date", "fieldtype": "Date", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Days Overdue"), "fieldname": "days_overdue", "fieldtype": "Int", "width": 100},
		{"label": _("Outstanding"), "fieldname": "outstanding", "fieldtype": "Currency", "options": "currency", "width": 120},
	]
	columns += [
		{"label": _(label), "fieldname": fieldname, "fieldtype": "Currency", "options": "currency", "width": 110}
		for _limit, fieldname, label in BUCKETS
	]
	columns.append({"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1})
	return columns


def get_data(filters):
	conditions = {"docstatus": 1, "paid_amount": [">", 0]}
	for field in ("company", "employee", "department"):
		if filters.get(field):
			conditions[field] = filters.get(field)

	as_on = getdate(filters.get("as_on_date") or today())
	rows = []
	for row in frappe.get_list(
		"Employee Advance",
		filters=conditions,
		fields=[
			"name", "employee", "employee_name", "department", "purpose_type", "payment_date", "due_date",
			"paid_amount", "claimed_amount", "return_amount", "currency",
		],
		order_by="due_date asc",
		limit_page_length=0,
	):
		amount = outstanding(row)
		if amount <= 0:
			continue
		row.outstanding = amount
		row.days_overdue = max(date_diff(as_on, row.due_date), 0) if row.due_date else 0
		bucket = bucket_of(row.days_overdue)
		for _limit, fieldname, _label in BUCKETS:
			row[fieldname] = amount if fieldname == bucket else 0
		rows.append(row)
	return rows


def bucket_of(days_overdue: int) -> str:
	for limit, fieldname, _label in BUCKETS:
		if limit is None or days_overdue <= limit:
			return fieldname
	return BUCKETS[-1][1]
