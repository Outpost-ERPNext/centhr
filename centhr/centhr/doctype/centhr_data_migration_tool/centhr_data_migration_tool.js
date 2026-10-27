// Copyright (c) 2026, Outpost Work LLP and contributors
// For license information, please see license.txt

frappe.provide("centhr.migration");

const MIGRATION_METHOD =
	"centhr.centhr.doctype.centhr_data_migration_tool.centhr_data_migration_tool";

// Columns read from the CentHR site; `name` is the record name there
centhr.migration.SECTIONS = {
	// Listed in tree order, so parents are migrated before their children
	account: {
		doctype: "Account",
		label: __("Account"),
		filters: ["root_type"],
		columns: [
			["account_name", __("Account Name")],
			["account_number", __("Account Number")],
			["parent_account", __("Parent Account")],
			["root_type", __("Root Type")],
			["account_type", __("Account Type")],
			["is_group", __("Is Group"), "Check"],
		],
	},
	cost_center: {
		doctype: "Cost Center",
		label: __("Cost Center"),
		filters: [],
		columns: [
			["cost_center_name", __("Cost Center Name")],
			["cost_center_number", __("Cost Center Number")],
			["parent_cost_center", __("Parent Cost Center")],
			["is_group", __("Is Group"), "Check"],
			["disabled", __("Disabled"), "Check"],
		],
	},
	employee: {
		doctype: "Employee",
		label: __("Employee"),
		filters: ["status"],
		columns: [
			["employee_number", __("Employee Number")],
			["employee_name", __("Employee Name")],
			["status", __("Status")],
			["department", __("Department")],
			["date_of_joining", __("Date of Joining"), "Date"],
		],
	},
	leave_type: {
		doctype: "Leave Type",
		label: __("Leave Type"),
		filters: [],
		columns: [
			["leave_type_name", __("Leave Type Name")],
			["max_leaves_allowed", __("Max Leaves Allowed"), "Float"],
			["is_lwp", __("Leave Without Pay"), "Check"],
			["is_carry_forward", __("Carry Forward"), "Check"],
			["is_earned_leave", __("Earned Leave"), "Check"],
		],
	},
	leave_policy: {
		doctype: "Leave Policy",
		label: __("Leave Policy"),
		filters: [],
		columns: [
			["title", __("Title")],
			["docstatus", __("Submitted"), "Check"],
		],
	},
	leave_policy_assignment: {
		doctype: "Leave Policy Assignment",
		label: __("Leave Policy Assignment"),
		filters: ["from_date", "to_date", "employee"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["leave_policy", __("Leave Policy")],
			["effective_from", __("Effective From"), "Date"],
			["effective_to", __("Effective To"), "Date"],
		],
	},
	leave_allocation: {
		doctype: "Leave Allocation",
		label: __("Leave Allocation"),
		filters: ["from_date", "to_date", "employee", "leave_type"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["leave_type", __("Leave Type")],
			["from_date", __("From Date"), "Date"],
			["to_date", __("To Date"), "Date"],
			["new_leaves_allocated", __("New Leaves Allocated"), "Float"],
		],
	},
	leave_application: {
		doctype: "Leave Application",
		label: __("Leave Application"),
		filters: ["from_date", "to_date", "employee", "status"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["leave_type", __("Leave Type")],
			["from_date", __("From Date"), "Date"],
			["to_date", __("To Date"), "Date"],
			["status", __("Status")],
		],
	},
	attendance: {
		doctype: "Attendance",
		label: __("Attendance"),
		filters: ["from_date", "to_date", "employee", "status"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["attendance_date", __("Attendance Date"), "Date"],
			["status", __("Status")],
		],
	},
	salary_component: {
		doctype: "Salary Component",
		label: __("Salary Component"),
		filters: [],
		columns: [
			["salary_component", __("Salary Component")],
			["salary_component_abbr", __("Abbreviation")],
			["type", __("Type")],
			["disabled", __("Disabled"), "Check"],
		],
	},
	salary_structure: {
		doctype: "Salary Structure",
		label: __("Salary Structure"),
		filters: [],
		columns: [
			["is_active", __("Is Active")],
			["payroll_frequency", __("Payroll Frequency")],
			["docstatus", __("Submitted"), "Check"],
		],
	},
	salary_structure_assignment: {
		doctype: "Salary Structure Assignment",
		label: __("Salary Structure Assignment"),
		filters: ["from_date", "to_date", "employee"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["salary_structure", __("Salary Structure")],
			["from_date", __("From Date"), "Date"],
			["base", __("Base"), "Currency"],
			["docstatus", __("Submitted"), "Check"],
		],
	},
	additional_salary: {
		doctype: "Additional Salary",
		label: __("Additional Salary"),
		filters: ["employee", "salary_component"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["salary_component", __("Salary Component")],
			["amount", __("Amount"), "Currency"],
			["payroll_date", __("Payroll Date"), "Date"],
			["is_recurring", __("Recurring"), "Check"],
			["docstatus", __("Submitted"), "Check"],
		],
	},
	salary_slip: {
		doctype: "Salary Slip",
		label: __("Salary Slip"),
		filters: ["from_date", "to_date", "employee"],
		columns: [
			["employee", __("Employee")],
			["employee_name", __("Employee Name")],
			["start_date", __("Start Date"), "Date"],
			["end_date", __("End Date"), "Date"],
			["net_pay", __("Net Pay"), "Currency"],
			["docstatus", __("Submitted"), "Check"],
		],
	},
	payroll_entry: {
		doctype: "Payroll Entry",
		label: __("Payroll Entry"),
		filters: ["from_date", "to_date"],
		columns: [
			["posting_date", __("Posting Date"), "Date"],
			["start_date", __("Start Date"), "Date"],
			["end_date", __("End Date"), "Date"],
			["payroll_frequency", __("Payroll Frequency")],
			["number_of_employees", __("Employees"), "Int"],
			["docstatus", __("Submitted"), "Check"],
		],
	},
};

const form_events = {
	setup(frm) {
		frm.migration_tables = {};
		for (const [section, config] of Object.entries(centhr.migration.SECTIONS)) {
			if (config.filters.includes("employee")) {
				frm.set_query(`${section}_employee`, () => ({ filters: { company: frm.doc.company } }));
			}
		}

		frappe.realtime.off("centhr_migration_progress");
		frappe.realtime.on("centhr_migration_progress", (data) => {
			frm.migration_tables[data.section]?.update_row(data);
		});
		frappe.realtime.off("centhr_migration_stopped");
		frappe.realtime.on("centhr_migration_stopped", (data) => {
			frm.migration_tables[data.section]?.on_stopped(data);
		});
	},

	onload(frm) {
		if (!frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_default("company"));
		}

		const today = frappe.datetime.get_today();
		for (const [section, config] of Object.entries(centhr.migration.SECTIONS)) {
			if (config.filters.includes("from_date") && !frm.doc[`${section}_from_date`]) {
				frm.doc[`${section}_from_date`] = frappe.datetime.add_months(today, -1);
				frm.doc[`${section}_to_date`] = today;
			}
		}
	},

	refresh(frm) {
		frm.disable_save();
		frm.trigger("render_migration_order");
		frm.trigger("set_connected_site");

		for (const section of Object.keys(centhr.migration.SECTIONS)) {
			if (!frm.migration_tables[section]) {
				frm.migration_tables[section] = new centhr.migration.MigrationTable(frm, section);
			}
		}
	},

	company(frm) {
		frm.trigger("set_connected_site");
		for (const table of Object.values(frm.migration_tables)) {
			table.reset();
		}
	},

	set_connected_site(frm) {
		frm.set_intro("");
		if (!frm.doc.company) return;

		frappe.db.get_doc("CentHr Settings").then((settings) => {
			const target = (settings.authorization || []).find((row) => row.company === frm.doc.company);
			if (target) {
				frm.set_intro(
					__("Records are read from {0} and created on this site for company {1}.", [
						`<b>${frappe.utils.escape_html(target.base_url)}</b>`,
						`<b>${frappe.utils.escape_html(frm.doc.company)}</b>`,
					]),
					"blue"
				);
			} else {
				frm.set_intro(
					__("Company {0} has no connected CentHR site. Add it in {1}.", [
						`<b>${frappe.utils.escape_html(frm.doc.company)}</b>`,
						`<a href="/app/centhr-settings">${__("CentHr Settings")}</a>`,
					]),
					"red"
				);
			}
		});
	},

	render_migration_order(frm) {
		const order = Object.values(centhr.migration.SECTIONS).map((config) => config.label);
		frm.get_field("migration_order").$wrapper.html(`
			<div class="text-muted small">
				<p>${__("Records depend on each other, so migrate the sections in this order:")}</p>
				<p><b>${order.join(" &rarr; ")}</b></p>
				<p>${__(
					"Fetch Details only reads the connected site. Nothing is created until you click Migrate. Records that already exist on this site are skipped, and every attempt is logged in CentHR API Logger."
				)}</p>
			</div>
		`);
	},
};

// "Fetch Details" button of each section
for (const section of Object.keys(centhr.migration.SECTIONS)) {
	form_events[`${section}_fetch`] = (frm) => frm.migration_tables[section].fetch();
}

frappe.ui.form.on("Centhr Data Migration Tool", form_events);

centhr.migration.MigrationTable = class MigrationTable {
	constructor(frm, section) {
		this.frm = frm;
		this.section = section;
		this.config = centhr.migration.SECTIONS[section];
		this.$summary = frm.get_field(`${section}_summary`).$wrapper;
		this.$table = frm.get_field(`${section}_table`).$wrapper;
		this.reset();
	}

	reset() {
		this.records = [];
		this.datatable = null;
		this.running = false;
		this.stopping = false;
		this.$table.empty();
		this.$summary.html(
			`<div class="text-muted">${__("Set the filters and click Fetch Details.")}</div>`
		);
	}

	fetch() {
		const filters = this.get_filters();
		if (!this.frm.doc.company) {
			frappe.throw(__("Select a Company first"));
		}
		if (filters.from_date && filters.to_date && filters.from_date > filters.to_date) {
			frappe.throw(__("From Date cannot be after To Date"));
		}

		return frappe
			.call({
				method: `${MIGRATION_METHOD}.get_records`,
				args: { section: this.section, company: this.frm.doc.company, filters },
				freeze: true,
				freeze_message: __("Fetching {0} records from the CentHR site...", [this.config.label]),
			})
			.then((r) => {
				this.records = r.message.records;
				// a migration started earlier, e.g. before the page was reloaded, can still be stopped
				this.running = r.message.running;
				this.render();
			});
	}

	get_filters() {
		const filters = {};
		for (const key of this.config.filters) {
			filters[key] = this.frm.doc[`${this.section}_${key}`] || null;
		}
		return filters;
	}

	render() {
		this.render_summary();
		this.$table.empty();
		if (!this.records.length) return;

		this.datatable = new frappe.DataTable(this.$table.get(0), {
			columns: this.get_columns(),
			data: this.get_data(),
			checkboxColumn: true,
			inlineFilters: true,
			dynamicRowHeight: true,
			layout: "fluid",
		});
		this.$table.find(".dt-scrollable").css("max-height", "calc(100vh - 400px)");
	}

	render_summary() {
		if (!this.records.length) {
			this.$summary.html(
				`<div class="text-muted text-center p-4">${__("No matching records found")}</div>`
			);
			return;
		}

		const counts = {};
		for (const record of this.records) {
			counts[record.migration_status] = (counts[record.migration_status] || 0) + 1;
		}
		const pills = Object.entries(counts)
			.map(([status, count]) => this.get_status_pill(status, `${__(status)}: ${count}`))
			.join(" ");

		this.$summary.html(`
			<div class="flex justify-between align-center flex-wrap mb-3" style="gap: var(--padding-sm)">
				<div>
					<b>${__("{0} records fetched", [this.records.length])}</b>
					<span class="ml-2">${pills}</span>
				</div>
				<div>${this.get_action_buttons()}</div>
			</div>
		`);
		this.$summary.find(".migrate-selected").on("click", () => this.migrate_selected());
		this.$summary.find(".migrate-pending").on("click", () => this.migrate_pending());
		this.$summary.find(".stop-migration").on("click", () => this.stop());
	}

	get_action_buttons() {
		if (this.running) {
			return `<button class="btn btn-danger btn-sm stop-migration" ${this.stopping ? "disabled" : ""}>
				${this.stopping ? __("Stopping...") : __("Stop Migration")}
			</button>`;
		}
		return `
			<button class="btn btn-default btn-sm migrate-selected">${__("Migrate Selected")}</button>
			<button class="btn btn-primary btn-sm migrate-pending">${__("Migrate Pending & Failed")}</button>
		`;
	}

	get_columns() {
		const columns = [{ name: __("CentHR Record"), width: 160 }];
		for (const [, label, fieldtype] of this.config.columns) {
			columns.push({
				name: label,
				editable: false,
				format: fieldtype ? (value) => frappe.format(value, { fieldtype }) : undefined,
			});
		}
		columns.push(
			{ name: __("Migration Status"), width: 150 },
			{ name: __("Record on This Site"), width: 160 }
		);
		return columns.map((column) => ({ editable: false, focusable: false, ...column }));
	}

	get_data() {
		return this.records.map((record) => [
			record.name,
			...this.config.columns.map(([fieldname]) => record[fieldname]),
			this.format_status(record),
			record.local_name
				? `<a href="/app/${frappe.router.slug(this.config.doctype)}/${encodeURIComponent(
						record.local_name
				  )}">${frappe.utils.escape_html(record.local_name)}</a>`
				: "",
		]);
	}

	format_status(record) {
		const status = record.migration_status;
		const pill = this.get_status_pill(status, __(status), record.error);
		return record.log
			? `<a href="/app/centhr-api-logger/${encodeURIComponent(record.log)}">${pill}</a>`
			: pill;
	}

	get_status_pill(status, label, title) {
		const colors = {
			Pending: "gray",
			Queued: "orange",
			Success: "green",
			Failed: "red",
			"Already Exists": "blue",
		};
		const title_attr = title ? `title="${frappe.utils.escape_html(title)}"` : "";
		return `<span class="indicator-pill ${colors[status] || "gray"}" ${title_attr}>${label}</span>`;
	}

	migrate_selected() {
		// In table order, so parents in a tree are migrated before their children
		const indexes = this.datatable.rowmanager
			.getCheckedRows()
			.map(Number)
			.sort((a, b) => a - b);
		if (!indexes.length) {
			frappe.throw(__("Select the records to migrate"));
		}
		this.migrate(indexes.map((index) => this.records[index]));
	}

	migrate_pending() {
		const records = this.records.filter((record) =>
			["Pending", "Failed"].includes(record.migration_status)
		);
		if (!records.length) {
			frappe.throw(__("There are no pending or failed records"));
		}
		this.migrate(records);
	}

	migrate(records) {
		// Records already on this site are skipped by the server too; this saves the round trip
		const names = records
			.filter((record) => !["Success", "Already Exists", "Queued"].includes(record.migration_status))
			.map((record) => record.name);
		if (!names.length) {
			frappe.throw(__("The selected records are already on this site"));
		}

		frappe.confirm(
			__("Migrate {0} {1} records from the CentHR site to this site?", [
				names.length,
				this.config.label,
			]),
			() =>
				frappe
					.call({
						method: `${MIGRATION_METHOD}.migrate_records`,
						args: { section: this.section, company: this.frm.doc.company, names },
						freeze: true,
					})
					.then(() => {
						this.running = true;
						this.stopping = false;
						this.set_status(names, { migration_status: "Queued" });
						frappe.show_alert({
							message: __("Migration of {0} records started", [names.length]),
							indicator: "blue",
						});
					})
		);
	}

	update_row(data) {
		this.set_status([data.name], {
			migration_status: data.status,
			error: data.error,
			log: data.log,
			local_name: data.local_name,
		});

		const dialog = frappe.show_progress(
			__("Migrating {0}", [this.config.label]),
			data.index,
			data.total,
			__("{0} of {1}", [data.index, data.total])
		);
		if (!this.stopping && !dialog.has_primary_action) {
			dialog.set_primary_action(__("Stop Migration"), () => this.stop());
			dialog.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
		}
		if (data.index === data.total) {
			this.running = false;
			this.stopping = false;
			this.refresh_soon();
			frappe.hide_progress();
			frappe.show_alert({ message: __("{0} migration finished", [this.config.label]), indicator: "green" });
		}
	}

	stop() {
		frappe.confirm(
			__(
				"Stop the {0} migration? The record being migrated now still finishes, and the rest stay pending so you can migrate them later.",
				[this.config.label]
			),
			() =>
				frappe
					.call({
						method: `${MIGRATION_METHOD}.stop_migration`,
						args: { section: this.section, company: this.frm.doc.company },
					})
					.then(() => {
						this.stopping = true;
						this.render_summary();
						const dialog = frappe.cur_progress;
						dialog?.get_primary_btn().prop("disabled", true).html(__("Stopping..."));
						frappe.show_alert({
							message: __("Stopping the {0} migration...", [this.config.label]),
							indicator: "orange",
						});
					})
		);
	}

	on_stopped(data) {
		this.running = false;
		this.stopping = false;
		this.set_status(data.names, { migration_status: "Pending" });
		frappe.hide_progress();
		frappe.show_alert({
			message: __("{0} migration stopped. {1} records were not migrated.", [
				this.config.label,
				data.names.length,
			]),
			indicator: "orange",
		});
	}

	set_status(names, values) {
		const name_set = new Set(names);
		for (const record of this.records) {
			if (name_set.has(record.name)) Object.assign(record, values);
		}
		this.refresh_soon();
	}

	refresh_soon() {
		// Progress arrives once per record; redraw at most a few times a second
		clearTimeout(this.refresh_timer);
		this.refresh_timer = setTimeout(() => {
			this.render_summary();
			this.datatable?.refresh(this.get_data(), this.get_columns());
		}, 300);
	}
};
