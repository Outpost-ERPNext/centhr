import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

CUSTOM_FIELDS = {
	"Company": [
		{
			"fieldname": "payroll_cycle_start_day",
			"fieldtype": "Int",
			"label": "Payroll Cycle Start Day",
			"insert_after": "default_payroll_payable_account",
			"non_negative": 1,
			"description": "Day of the month the pay cycle starts, 1 to 28. With 20, the July cycle runs from 20 June to 19 July. Leave 0 or 1 for calendar months.",
		},
		{
			"fieldname": "auto_recover_advances",
			"fieldtype": "Check",
			"label": "Recover Overdue Advances in Payroll",
			"insert_after": "payroll_cycle_start_day",
			"description": "When payroll is generated, overdue employee advances are deducted from the salary of that cycle.",
		},
	],
	"Payroll Entry": [
		{
			"fieldname": "centhr_batch",
			"fieldtype": "Select",
			"label": "Payroll Batch",
			"options": "Regular\nExited",
			"default": "Regular",
			"insert_after": "payroll_frequency",
			"read_only": 1,
			"description": "Exited: only employees whose relieving date is in the pay cycle.",
		},
	],
	"Employee": [
		{
			"fieldname": "custom_no_line_manager",
			"fieldtype": "Check",
			"label": "No Line Manager",
			"insert_after": "designation",
			"description": "Tick for an employee who reports to nobody. Otherwise Reports To is required.",
		},
	],
}


def create_custom_fields():
	for doctype, fields in CUSTOM_FIELDS.items():
		for field in fields:
			if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field["fieldname"]}):
				create_custom_field(doctype, field)
				frappe.db.commit()
				frappe.clear_cache(doctype=doctype)
	# The form asks for Reports To unless No Line Manager is ticked
	make_property_setter(
		"Employee",
		"reports_to",
		"mandatory_depends_on",
		"eval:!doc.custom_no_line_manager",
		"Data",
		validate_fields_for_doctype=False,
	)


def validate_line_manager(doc, method=None):
	"""A new employee names their line manager, or says they have none. Employees that exist already,
	and those copied in by the Data Migration Tool, are not held to it."""
	if doc.custom_no_line_manager:
		doc.reports_to = None
		return
	if (
		doc.is_new()
		and not doc.reports_to
		and not (frappe.flags.centhr_migration or doc.flags.ignore_mandatory)
	):
		frappe.throw(
			_("Choose who {0} reports to, or tick No Line Manager.").format(
				doc.employee_name or _("the employee")
			),
			title=_("Line Manager Missing"),
		)
