import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# ABBR resolves to the employee's Company.abbr (erpnext naming_series_variables hook)
EMPLOYEE_NAMING_SERIES = ".ABBR.-EMP-.#####"


def create_custom_fields():
	custom_fields = {
		"Holiday List": [
			{
				"fieldname": "company",
				"fieldtype": "Link",
				"label": "Company",
				"options": "Company",
				"insert_after": "total_holidays",
                "reqd": 1,
			},
            {
                "fieldname": "is_active",
                "fieldtype": "Check",
                "label": "Is Active",
                "insert_after": "company",
            }
   
		]
	}

	for doctype, fields in custom_fields.items():
		for field in fields:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
				create_custom_field(doctype, field)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)

	set_employee_naming_series()


def set_employee_naming_series():
	for prop in ("options", "default"):
		make_property_setter(
			"Employee", "naming_series", prop, EMPLOYEE_NAMING_SERIES, "Text", validate_fields_for_doctype=False
		)
	frappe.clear_cache(doctype="Employee")


def delete_custom_fields():
	custom_fields_to_delete = {"Holiday List": ["company", "is_active"]}

	for doctype, fields in custom_fields_to_delete.items():
		for field_name in fields:
			if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name}):
				frappe.delete_doc("Custom Field", f"{doctype}-{field_name}", ignore_missing=True)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)

	frappe.db.delete(
		"Property Setter",
		{"doc_type": "Employee", "field_name": "naming_series", "property": ("in", ["options", "default"])},
	)
	frappe.clear_cache(doctype="Employee")


def validate_cross_company(doc, method=None):
	if not doc.cross_company_reports:
		doc.cross_company = None
		return
	if doc.cross_company == doc.company:
		frappe.throw(_("Employee Company and Cross Reporting Company cannot be the same"))
