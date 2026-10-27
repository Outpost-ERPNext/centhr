frappe.ready(function () {
	const web_form = frappe.web_form;
	const EMPLOYEES_METHOD = "centhr.centhr.web_form.leave_application.leave_application.get_employees";
	const REASONS = ["Work From Home", "On Duty"];
	const MAX_DAYS = 31;

	// One row per day between From Date and To Date; each becomes its own Attendance Request
	let rows = [];
	// Parent Reason and Explanation as last copied into the rows
	let parent = { reason: web_form.get_value("reason") || "", explanation: "" };

	const $regularization = $(`
		<div class="checkbox">
			<label>
				<input type="checkbox" class="regularization-check" checked>
				<span class="label-area">${__("Attendance Regularization Request")}</span>
			</label>
		</div>
	`).appendTo(web_form.fields_dict.regularization_html.$wrapper.empty());

	const $confirmation = $(`
		<div class="form-group">
			<label class="control-label reqd">${__("Employee Code Confirmation")}</label>
			<input type="text" class="form-control confirmation-input" autocomplete="off">
		</div>
	`).appendTo(web_form.fields_dict.confirmation_html.$wrapper.empty());

	const $request_dates = web_form.fields_dict.request_dates_html.$wrapper.empty();

	// The page lists every employee; narrow them to the company
	set_employee_options([]);
	render_rows();

	function set_employee_options(options) {
		web_form.fields_dict.employee.set_data(options);
	}

	function set_employees() {
		const company = web_form.get_value("company");
		web_form.set_value("employee", "");
		set_employee_options([]);
		if (!company) return;

		frappe
			.call({ method: EMPLOYEES_METHOD, args: { company } })
			.then((r) => set_employee_options(r.message));
	}

	function set_employee_name() {
		// Guests cannot read Employee, so take the name from the option label "Name (ID)"
		const employee = web_form.get_value("employee");
		const option = web_form.fields_dict.employee.get_data().find((o) => o.value === employee);
		const name = option ? option.label.replace(new RegExp(` \\(${escape_regex(employee)}\\)$`), "") : "";
		web_form.set_value("employee_name", name);
		$confirmation.find(".confirmation-input").val("");
	}

	function escape_regex(text) {
		return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
	}

	function set_rows() {
		const from_date = web_form.get_value("from_date");
		const to_date = web_form.get_value("to_date");
		const days = from_date && to_date ? frappe.datetime.get_diff(to_date, from_date) + 1 : 0;
		if (days > MAX_DAYS) {
			frappe.msgprint(__("Request at most {0} days at a time.", [MAX_DAYS]));
			web_form.set_value("to_date", "");
			return;
		}

		// Keep what was edited in rows whose date is still in the range
		const existing = Object.fromEntries(rows.map((row) => [row.request_date, row]));
		rows = [];
		for (let i = 0; i < days; i++) {
			const request_date = frappe.datetime.add_days(from_date, i);
			rows.push(
				existing[request_date] || {
					request_date,
					reason: parent.reason,
					explanation: parent.explanation,
				}
			);
		}
		render_rows();
	}

	function copy_to_rows(fieldname) {
		const value = web_form.get_value(fieldname) || "";
		// Rows the user changed by hand keep their own value
		rows.filter((row) => row[fieldname] === parent[fieldname]).forEach((row) => (row[fieldname] = value));
		parent[fieldname] = value;
		render_rows();
	}

	function render_rows() {
		const reason_options = (selected) =>
			[""]
				.concat(REASONS)
				.map(
					(reason) =>
						`<option value="${reason}" ${reason === selected ? "selected" : ""}>${__(reason)}</option>`
				)
				.join("");

		const body = rows.length
			? rows
					.map(
						(row, idx) => `
				<tr data-idx="${idx}">
					<td class="row-no">${idx + 1}</td>
					<td>${frappe.datetime.str_to_user(row.request_date)}</td>
					<td><select class="form-control row-reason">${reason_options(row.reason)}</select></td>
					<td><input type="text" class="form-control row-explanation"
						value="${frappe.utils.escape_html(row.explanation || "")}"></td>
				</tr>`
					)
					.join("")
			: `<tr><td colspan="4" class="no-data">${__("Select From Date and To Date")}</td></tr>`;

		$request_dates.html(`
			<label class="control-label">${__("Request Dates")}</label>
			<div class="request-dates-grid">
				<table class="table">
					<thead><tr>
						<th class="row-no">${__("No.")}</th>
						<th>${__("Request Date")}</th>
						<th>${__("Reason")}</th>
						<th>${__("Explanation")}</th>
					</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	$request_dates.on("change", ".row-reason", function () {
		rows[$(this).closest("tr").data("idx")].reason = $(this).val();
	});
	$request_dates.on("input", ".row-explanation", function () {
		rows[$(this).closest("tr").data("idx")].explanation = $(this).val();
	});

	web_form.validate = () => {
		const employee = web_form.get_value("employee");
		const confirmation = ($confirmation.find(".confirmation-input").val() || "").trim();

		if (!$regularization.find(".regularization-check").is(":checked")) {
			frappe.msgprint(__("Tick Attendance Regularization Request to submit."));
			return false;
		}
		if (employee && confirmation !== employee) {
			frappe.msgprint(__("Employee Code Confirmation does not match the selected employee."));
			return false;
		}
		if (!rows.length) {
			frappe.msgprint(__("Select From Date and To Date to add Request Dates."));
			return false;
		}
		if (rows.some((row) => !row.reason)) {
			frappe.msgprint(__("Select a Reason for every Request Date."));
			return false;
		}

		// Sent with the form data; the server makes one Attendance Request per row
		web_form.doc.employee_code_confirmation = confirmation;
		web_form.doc.request_dates = rows.map(({ request_date, reason, explanation }) => ({
			request_date,
			reason,
			explanation,
		}));
		return true;
	};

	web_form.on("company", set_employees);
	web_form.on("employee", set_employee_name);
	web_form.on("from_date", set_rows);
	web_form.on("to_date", set_rows);
	web_form.on("reason", () => copy_to_rows("reason"));
	web_form.on("explanation", () => copy_to_rows("explanation"));
});
