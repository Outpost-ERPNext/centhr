// Copyright (c) 2026, Outpost Work LLP and contributors
// For license information, please see license.txt

frappe.query_reports["IOU Advance Summary"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company", default: frappe.defaults.get_user_default("Company") },
		{ fieldname: "as_on_date", label: __("As On Date"), fieldtype: "Date", default: frappe.datetime.get_today() },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
	],
};
