import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

# The fields of the CentHR sites, with the same fieldnames, so the Data Migration Tool copies their values
CUSTOM_FIELDS = {
	"Employee Advance": [
		{
			"fieldname": "payment_date",
			"fieldtype": "Date",
			"label": "Payment Date",
			"read_only": 1,
			"insert_after": "posting_date",
		},
		{
			"fieldname": "due_date",
			"fieldtype": "Date",
			"label": "Due Date",
			"read_only": 1,
			"allow_on_submit": 1,
			"insert_after": "payment_date",
		},
		{
			# HRMS v16 removed this field, but its Payment Entry code still reads it for foreign currency advances
			"fieldname": "exchange_rate",
			"fieldtype": "Float",
			"label": "Exchange Rate",
			"precision": "9",
			"default": "1",
			"depends_on": "currency",
			"print_hide": 1,
			"insert_after": "column_break_crso",
		},
		{
			"fieldname": "tenure",
			"fieldtype": "Data",
			"label": "Tenure",
			"insert_after": "purpose",
		},
		{
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"label": "Cost Center",
			"options": "Cost Center",
			"allow_on_submit": 1,
			"insert_after": "repay_unclaimed_amount_from_salary",
		},
		{
			"fieldname": "bank_details",
			"fieldtype": "Section Break",
			"label": "Bank Details",
			"insert_after": "cost_center",
		},
		{
			"fieldname": "bank_name",
			"fieldtype": "Data",
			"label": "Bank Name",
			"read_only": 1,
			"fetch_from": "employee.bank_name",
			"fetch_if_empty": 1,
			"insert_after": "bank_details",
		},
		{
			"fieldname": "bank_ac_no",
			"fieldtype": "Data",
			"label": "Bank AC No",
			"read_only": 1,
			"fetch_from": "employee.bank_ac_no",
			"fetch_if_empty": 1,
			"insert_after": "bank_name",
		},
		{
			"fieldname": "iou_and_loans",
			"fieldtype": "Data",
			"label": "IOU and Loans",
			"hidden": 1,
			"insert_after": "amended_from",
		},
	]
}


def create_custom_fields():
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
				create_custom_field(doctype, field)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)


def delete_custom_fields():
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
				frappe.delete_doc("Custom Field", f"{doctype}-{field['fieldname']}", ignore_missing=True)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)
