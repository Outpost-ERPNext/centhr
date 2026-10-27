import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# ABBR resolves to the employee's Company.abbr (erpnext naming_series_variables hook)
EMPLOYEE_NAMING_SERIES = ".ABBR.-EMP-.#####"


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
			{
				"fieldname":"cross_company_reports",
				"fieldtype":"Check",
				"label":"Cross Company Reports",
				"insert_after":"reports_to",
				"description":"Check this box if the employee reports to employees from other company."
			},
			{
				"fieldname":"cross_company",
				"fieldtype":"Link",
				"label":"Cross Company",
				"options":"Company",
				"insert_after":"cross_company_reports",
				"depends_on":"eval:doc.cross_company_reports == 1",
				"mandatory_depends_on":"eval:doc.cross_company_reports == 1"
    
			},
			{
				"fieldname":"salary_structure",
				"fieldtype":"Link",
				"label":"Salary Structure",
				"options":"Salary Structure",
				"insert_after":"salary_mode",
					"reqd":1
			},
			{
				"fieldname":"employee_base",
				"fieldtype":"Float",
				"label":"Employee Base",
				"insert_after":"salary_structure",
				"reqd":1
			},
			{
				"fieldname":"from_date",
				"fieldtype":"Date",
				"label":"From Date",
				"insert_after":"employee_base",
				"reqd":1
			},
			{
				"fieldname":"payroll_payable_account",
				"fieldtype":"Link",
				"label":"Payroll Payable Account",
				"options":"Account",
				"insert_after":"from_date",
				"reqd":1,
				"link_filters": '[["Account","account_type","=","Payable"]]'
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
	custom_fields_to_delete = {"Employee": ["territory", "cost_center", "channel", "cross_company_reports", "cross_company", "salary_structure", "employee_base", "from_date", "payroll_payable_account"]}

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
