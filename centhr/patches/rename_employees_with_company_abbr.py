import frappe

from centhr.customization.employee import set_employee_naming_series


def execute():
	"""Rename employees to {company abbr}-EMP-#####, numbered per company."""
	set_employee_naming_series()

	for company, abbr in frappe.get_all("Company", fields=["name", "abbr"], as_list=True):
		prefix = f"{abbr}-EMP-"
		employees = frappe.get_all(
			"Employee", filters={"company": company}, fields=["name", "employee_number"], order_by="name asc"
		)
		count = len([e for e in employees if e.name.startswith(prefix)])

		for employee in employees:
			if employee.name.startswith(prefix):
				continue

			# keep the old ID as the external sync matching key
			if not employee.employee_number:
				frappe.db.set_value("Employee", employee.name, "employee_number", employee.name, update_modified=False)

			count += 1
			new_name = f"{prefix}{count:05d}"
			frappe.rename_doc("Employee", employee.name, new_name, force=True, show_alert=False)
			frappe.db.set_value("Employee", new_name, "employee", new_name, update_modified=False)

		if count:
			set_series_counter(prefix, count)


def set_series_counter(prefix, current):
	if frappe.db.exists("Series", prefix):
		frappe.db.set_value("Series", prefix, "current", current, update_modified=False)
	else:
		frappe.db.sql("insert into `tabSeries` (name, current) values (%s, %s)", (prefix, current))
