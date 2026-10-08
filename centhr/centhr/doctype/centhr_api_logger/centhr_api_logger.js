// Copyright (c) 2026, Outpost Work LLP and contributors
// For license information, please see license.txt

frappe.ui.form.on("CentHR API Logger", {
	refresh(frm) {
		if (frm.doc.status !== "Failed" || frm.doc.resynced) {
			return;
		}

		const resync_error = frm.doc.__onload?.resync_error;
		if (resync_error) {
			frm.set_intro(resync_error, "orange");
			return;
		}

		frm.add_custom_button(__("Resync"), () => {
			frm.call("resync").then(() => {
				frappe.show_alert({ message: __("Resync queued"), indicator: "green" });
				frm.reload_doc();
			});
		});
	},
});
