import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

CUSTOM_FIELDS = {
	"Payroll Entry": [
		{
			"fieldname": "channel",
			"fieldtype": "Link",
			"label": "Channel",
			"options": "Channel",
			"insert_after": "designation",
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
