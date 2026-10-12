frappe.ui.form.on("Employee", {
	onload(frm) {
		frm.set_query("reports_to", () => {
			const filters = [
				["status", "=", "Active"],
				["name", "!=", frm.doc.name],
			];
			if (frm.doc.cross_company_reports && frm.doc.cross_company) {
				filters.push(["company", "=", frm.doc.cross_company]);
			}
			return { query: "erpnext.controllers.queries.employee_query", filters };
		});
	},

	cross_company(frm) {
		if (frm.doc.cross_company && frm.doc.cross_company === frm.doc.company) {
			frappe.msgprint({
				title: __("Invalid Company"),
				indicator: "red",
				message: __("Employee Company and Cross Reporting Company cannot be the same"),
			});
			frm.set_value("cross_company", "");
		}
		frm.set_value("reports_to", "");
	},

	cross_company_reports(frm) {
		if (!frm.doc.cross_company_reports) {
			frm.set_value("cross_company", "");
		}
		frm.set_value("reports_to", "");
	},
});
