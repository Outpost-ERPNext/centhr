// Copyright (c) 2026, Outpost Work LLP and contributors
// For license information, please see license.txt

frappe.listview_settings["CentHR API Logger"] = {
	onload(listview) {
		listview.page.add_action_item(__("Resync"), () => {
			const names = listview.get_checked_items(true);
			frappe
				.xcall("centhr.centhr.doctype.centhr_api_logger.centhr_api_logger.resync_logs", { names })
				.then((count) => {
					frappe.show_alert({
						message: __("{0} resync job(s) queued", [count]),
						indicator: count ? "green" : "orange",
					});
					listview.refresh();
				});
		});
	},
};
