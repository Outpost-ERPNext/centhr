// IOU Claim Settlement (SOP/AP/003). The server allocates the IOU again in centhr.iou.claim.
frappe.ready(function () {
	const web_form = frappe.web_form;
	const EMPLOYEES = "centhr.centhr.web_form.leave_application.leave_application.get_employees";
	const METHOD = "centhr.centhr.web_form.iou_claim.iou_claim";

	web_form.fields_dict.employee.set_data([]);
	let iou = null;

	function set_employees() {
		const company = web_form.get_value("company");
		web_form.set_value("employee", "");
		web_form.fields_dict.employee.set_data([]);
		if (!company) return;
		frappe
			.call({ method: EMPLOYEES, args: { company } })
			.then((r) => web_form.fields_dict.employee.set_data(r.message));
	}

	function load_iou() {
		const employee = web_form.get_value("employee");
		iou = null;
		render();
		if (!employee) return;

		frappe.call({ method: `${METHOD}.get_open_iou`, args: { employee } }).then((r) => {
			iou = r.message && r.message.name ? r.message : null;
			if (!iou && !web_form.get_value("claim_from_pocket")) {
				frappe.msgprint(
					__("You have no open IOU to settle. Tick 'Claim Expense from Pocket' to claim expenses you paid yourself."),
					__("No Open IOU")
				);
			}
			render();
		});
	}

	function money(value) {
		const currency = (iou && iou.currency) || "";
		return `${currency} ${format_number(value || 0, null, 2)}`.trim();
	}

	function total() {
		return (web_form.get_value("expenses") || []).reduce((sum, row) => sum + (flt(row.amount) || 0), 0);
	}

	function render() {
		const from_pocket = web_form.get_value("claim_from_pocket");
		const linked = !from_pocket && iou;
		web_form.fields_dict.iou_html.$wrapper.html(
			linked
				? `<p class="small">${__("Linked IOU")}: <b>${frappe.utils.escape_html(iou.name)}</b> &middot; ${__("Outstanding")}: <b>${money(iou.outstanding_amount)}</b>${iou.due_date ? ` &middot; ${__("Due")}: ${frappe.datetime.str_to_user(iou.due_date)}` : ""}</p>`
				: ""
		);

		const claimed = total();
		const outstanding = linked ? flt(iou.outstanding_amount) : 0;
		const pocket = Math.max(claimed - outstanding, 0);
		web_form.fields_dict.totals_html.$wrapper.html(
			`<p class="small">${__("Total Amount")}: <b>${money(claimed)}</b>${linked ? ` &middot; ${__("Settled from IOU")}: <b>${money(Math.min(claimed, outstanding))}</b>` : ""} &middot; ${__("Amount from Pocket")}: <b>${money(pocket)}</b></p>`
		);
	}

	web_form.validate = () => {
		if (!web_form.get_value("claim_from_pocket") && !iou) {
			frappe.msgprint(
				__("You have no open IOU to settle. Tick 'Claim Expense from Pocket' to claim expenses you paid yourself."),
				__("No Open IOU")
			);
			return false;
		}
		const missing = (web_form.get_value("expenses") || []).findIndex((row) => !row.attachment);
		if (missing >= 0) {
			frappe.msgprint(__("Row {0}: attach the invoice or receipt stamped by Finance.", [missing + 1]), __("Attachment Required"));
			return false;
		}
		return true;
	};

	web_form.on("company", set_employees);
	web_form.on("employee", load_iou);
	web_form.on("claim_from_pocket", render);
	web_form.on("expenses", render);
});
