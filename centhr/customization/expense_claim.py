import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

# CentHR keeps Channel and Department as accounting dimensions in the child tables
DIMENSION_FIELDS = [
	{
		"fieldname": "channel",
		"fieldtype": "Link",
		"label": "Channel",
		"options": "Channel",
		"insert_after": "accounting_dimensions_section",
	},
	{
		"fieldname": "department",
		"fieldtype": "Link",
		"label": "Department",
		"options": "Department",
		"insert_after": "dimension_col_break",
	},
]

# The fields of the CentHR sites, with the same fieldnames, so the Data Migration Tool copies their values
CUSTOM_FIELDS = {
	"Expense Claim": [
		{
			"fieldname": "expense_claim_request_date",
			"fieldtype": "Date",
			"label": "Expense Claim Request Date",
			"read_only": 1,
			"insert_after": "posting_date",
		},
		{
			# Required on CentHR, but optional here so claims made without a channel can still be saved
			"fieldname": "channel",
			"fieldtype": "Link",
			"label": "Channel",
			"options": "Channel",
			"insert_after": "accounting_dimensions_section",
		},
		{
			"fieldname": "iou_and_loans",
			"fieldtype": "Data",
			"label": "IOU and Loans",
			"hidden": 1,
			"insert_after": "amended_from",
		},
	],
	"Expense Claim Detail": DIMENSION_FIELDS,
	"Expense Taxes and Charges": DIMENSION_FIELDS,
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
