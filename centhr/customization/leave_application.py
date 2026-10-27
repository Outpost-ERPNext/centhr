import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

# Shown on the leave-application web form. They are mandatory there only, so Desk, the CentHR app
# and migrated records can still save a Leave Application without them.
CUSTOM_FIELDS = {
	"Leave Application": [
		{
			"fieldname": "request_type",
			"fieldtype": "Select",
			"label": "Request Type",
			"options": "Leave Application",
			"default": "Leave Application",
			"insert_after": "employee",
		},
		{
			"fieldname": "leaves_pending_approval",
			"fieldtype": "Float",
			"label": "Pending for Approval",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": "leave_balance",
		},
		{
			"fieldname": "leave_attachment",
			"fieldtype": "Attach",
			"label": "Leave Attachment",
			"no_copy": 1,
			"insert_after": "description",
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
