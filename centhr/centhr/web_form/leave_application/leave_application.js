frappe.ready(function () {
	const web_form = frappe.web_form;
	const METHOD = "centhr.centhr.web_form.leave_application.leave_application";

	// The page lists every employee and leave type; narrow them to the company and the employee
	set_options("employee", []);
	set_options("leave_type", []);

	function set_options(fieldname, options) {
		web_form.fields_dict[fieldname].set_data(options);
	}

	function has_option(fieldname, value) {
		return web_form.fields_dict[fieldname].get_data().some((option) => option.value === value);
	}

	function set_employees() {
		const company = web_form.get_value("company");
		web_form.set_value("employee", "");
		set_options("employee", []);
		if (!company) return;

		frappe
			.call({ method: `${METHOD}.get_employees`, args: { company } })
			.then((r) => set_options("employee", r.message));
	}

	function set_leave_types() {
		const employee = web_form.get_value("employee");
		if (!employee) {
			web_form.set_value("leave_type", "");
			set_options("leave_type", []);
			return;
		}

		frappe
			.call({
				method: `${METHOD}.get_leave_types`,
				args: { employee, date: web_form.get_value("from_date") || null },
			})
			.then((r) => {
				set_options("leave_type", r.message);
				const leave_type = web_form.get_value("leave_type");
				if (leave_type && !has_option("leave_type", leave_type)) {
					web_form.set_value("leave_type", "");
				}
			});
	}

	// Leave Days are more than the balance HRMS lets this application use
	let insufficient = false;

	function set_leave_balance() {
		const employee = web_form.get_value("employee");
		const leave_type = web_form.get_value("leave_type");
		if (!employee || !leave_type) {
			web_form.set_value("leave_balance", 0);
			web_form.set_value("leaves_pending_approval", 0);
			web_form.set_value("total_leave_days", 0);
			show_insufficient(null);
			return;
		}

		frappe
			.call({
				method: `${METHOD}.get_leave_balance`,
				args: {
					employee,
					leave_type,
					date: web_form.get_value("from_date") || null,
					to_date: web_form.get_value("to_date") || null,
				},
			})
			.then((r) => {
				web_form.set_value("leave_balance", r.message.leave_balance);
				web_form.set_value("leaves_pending_approval", r.message.leaves_pending_approval);
				web_form.set_value("total_leave_days", r.message.leave_days);
				show_insufficient(r.message.insufficient ? r.message : null);
			});
	}

	function show_insufficient(result) {
		insufficient = Boolean(result);
		const $field = web_form.fields_dict.leave_balance.$wrapper;
		$field.find(".leave-balance-error").remove();
		if (!result) return;

		const message = __("Balance not enough: {0} day(s) applied, {1} available", [
			result.leave_days,
			result.available,
		]);
		$field.append(`<p class="leave-balance-error text-danger small">${frappe.utils.escape_html(message)}</p>`);
	}

	web_form.validate = () => {
		if (insufficient) {
			frappe.msgprint(__("Leave balance is not enough for the selected dates."), __("Balance Not Enough"));
			return false;
		}
		return true;
	};

	web_form.on("company", set_employees);
	web_form.on("employee", () => {
		set_leave_types();
		set_leave_balance();
	});
	web_form.on("leave_type", set_leave_balance);
	web_form.on("from_date", () => {
		set_leave_types();
		set_leave_balance();
	});
	web_form.on("to_date", set_leave_balance);
});
