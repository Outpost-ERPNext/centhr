// Only one holiday list per company is active; the server deactivates the others on save
frappe.ui.form.on("Holiday List", {
	async is_active(frm) {
		// A value set back after Cancel must not ask again
		if (frm._reverting_active) {
			frm._reverting_active = false;
			return;
		}
		const active = frm.doc.is_active;
		const company = frm.doc.company;
		let message;

		if (active) {
			if (!company) {
				frm._reverting_active = true;
				frm.set_value("is_active", 0);
				frappe.msgprint(__("Set a Company before you make this holiday list active"));
				return;
			}
			const current = await frappe.xcall("centhr.api.holiday_list.get_active_holiday_list", {
				company,
				exclude: frm.is_new() ? null : frm.doc.name,
			});
			message = current
				? __("{0} is the active holiday list for {1}. Make this list active instead? {0} is deactivated, and this list is applied to all employees of {1} when you save.", [
						current.bold(),
						company.bold(),
				  ])
				: __("Make this the active holiday list for {0}? It is applied to all employees of {0} when you save.", [company.bold()]);
		} else {
			message = __("{0} will have no active holiday list. Continue?", [(company || __("The company")).bold()]);
		}

		frappe.confirm(
			message,
			() => {},
			() => {
				frm._reverting_active = true;
				frm.set_value("is_active", active ? 0 : 1);
			}
		);
	},
});
