import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def create_custom_fields():
	custom_fields = {
		"Employee": [
			{
				"fieldname": "territory",
				"fieldtype": "Link",
				"label": "Territory",
				"options": "Territory",
				"insert_after": "branch",
			},
			{
				"fieldname": "cost_center",
				"fieldtype": "Link",
				"label": "Cost Center",
				"options": "Cost Center",
				"insert_after": "grade",
			},
			{
				"fieldname": "channel",
				"fieldtype": "Link",
				"label": "Channel",
				"options": "Channel",
				"insert_after": "cost_center",
			},
		]
	}

	for doctype, fields in custom_fields.items():
		for field in fields:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
				create_custom_field(doctype, field)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)


def delete_custom_fields():
	custom_fields_to_delete = {"Employee": ["territory", "cost_center", "channel"]}

	for doctype, fields in custom_fields_to_delete.items():
		for field_name in fields:
			if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name}):
				frappe.delete_doc("Custom Field", f"{doctype}-{field_name}", ignore_missing=True)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)
