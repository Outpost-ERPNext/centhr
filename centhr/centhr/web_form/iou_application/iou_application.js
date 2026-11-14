// IOU Application (SOP/AP/003). The server repeats every check in centhr.iou.advance.
frappe.ready(function () {
	const web_form = frappe.web_form;
	const EMPLOYEES = "centhr.centhr.web_form.leave_application.leave_application.get_employees";
	const METHOD = "centhr.centhr.web_form.iou_application.iou_application";

	web_form.fields_dict.employee.set_data([]);
	let blocked = null;

	function set_employees() {
		const company = web_form.get_value("company");
		web_form.set_value("employee", "");
		web_form.fields_dict.employee.set_data([]);
		if (!company) return;
		frappe
			.call({ method: EMPLOYEES, args: { company } })
			.then((r) => web_form.fields_dict.employee.set_data(r.message));
	}

	function load_status() {
		const employee = web_form.get_value("employee");
		blocked = null;
		show_status("");
		if (!employee) return;

		frappe.call({ method: `${METHOD}.get_iou_status`, args: { employee } }).then((r) => {
			const status = r.message || {};
			if (status.bank_name && !web_form.get_value("bank_name")) web_form.set_value("bank_name", status.bank_name);
			if (status.bank_ac_no && !web_form.get_value("bank_ac_no")) web_form.set_value("bank_ac_no", status.bank_ac_no);

			if (status.pending_iou) {
				blocked = __("Your IOU application {0} is still pending approval. You can apply for a new IOU once it is approved or rejected.", [status.pending_iou]);
			} else if (status.open_iou) {
				blocked = __("You have not settled IOU {0}. Settle it with an IOU claim before you apply for a new IOU.", [status.open_iou]);
			}
			show_status(blocked || __("No outstanding IOU."), Boolean(blocked));
		});
	}

	function show_status(message, error) {
		const html = message
			? `<p class="${error ? "text-danger" : "text-muted"} small">${frappe.utils.escape_html(message)}</p>`
			: "";
		web_form.fields_dict.outstanding_html.$wrapper.html(html);
	}

	web_form.validate = () => {
		if (blocked) {
			frappe.msgprint(blocked, __("Cannot Apply"));
			return false;
		}
		if (web_form.get_value("purpose_type") === "Travel" && !(parseInt(web_form.get_value("tenure")) > 0)) {
			frappe.msgprint(__("Enter the travel tenure as a number of days."), __("Tenure Required"));
			return false;
		}
		if (!web_form.get_value("iou_declaration")) {
			frappe.msgprint(__("Tick the declaration to apply for the IOU."), __("Declaration Required"));
			return false;
		}
		return true;
	};

	web_form.on("company", set_employees);
	web_form.on("employee", load_status);
});
