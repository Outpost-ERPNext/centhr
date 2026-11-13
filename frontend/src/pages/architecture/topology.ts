/**
 * The real CentHR integration topology, as wired in centhr/hooks.py and centhr/api/**.
 * Company sites come from CentHr Settings > Authorization at runtime; everything else is static.
 */

export type EdgeKind = "request" | "response" | "sync" | "internal"
export type NodeKind = "core" | "process" | "company" | "module"

export interface Site {
	company: string
	host: string | null
}

export interface ModuleDef {
	key: string
	label: string
	summary: string
	doctypes: string[]
	/** Doctypes CentHR pushes to the site */
	pushes: string[]
	/** doc_event hooks (HOOKS keys) that send this module's records */
	hooks: string[]
	push: string[]
	pull: string[]
	local: string[]
	notSynced: string[]
	files: string[]
}

export interface ProcessDef {
	key: string
	label: string
	summary: string
	points: string[]
	files: string[]
}

export interface GraphNode {
	id: string
	kind: NodeKind
	label: string
	company?: string
	module?: ModuleDef
	process?: ProcessDef
	site?: Site
	/** Column in the layered view */
	layer?: number
	/** Radius override */
	size?: number
}

export interface GraphEdge {
	id: string
	from: string
	to: string
	kind: EdgeKind
	/** Which way particles travel: 1 = from → to, -1 = to → from */
	flow: 1 | -1
	/** Curve bend, as a share of the edge length */
	bend: number
	title: string
	detail: string
	company?: string
}

export const EDGE_STYLES: Record<EdgeKind, { label: string; color: string; hint: string }> = {
	request: { label: "API request", color: "#38d9f5", hint: "CentHR → site · POST / PUT / DELETE and GET checks" },
	response: { label: "API response", color: "#2dd4bf", hint: "Site → CentHR · status logged in CentHR API Logger" },
	sync: { label: "Data migration", color: "#5b8cff", hint: "Site → CentHR · pulled by the Data Migration Tool" },
	internal: { label: "Internal", color: "#8b93c9", hint: "Inside CentHR · hooks, jobs and schedulers" },
}

export const CORE = {
	label: "CentHR",
	summary:
		"The central HRMS. HR records are created and approved here, then pushed to the HRMS site of their company. Data from a site comes in only through the Data Migration Tool.",
	responsibilities: [
		{ title: "Routes by company", text: "get_targets(company) picks the Authorization row of the record's company. Shift Type and Salary Component have no company, so they go once to every site." },
		{ title: "Queues every push", text: "doc_events in hooks.py enqueue a background job on the short queue after the commit, so a user never waits on a site." },
		{ title: "Authenticates and retries", text: "REST calls to /api/resource/<DocType> with token auth (api_key:api_secret), a (10, 30) s timeout, 2 retries and a Redis lock per record." },
		{ title: "Logs every call", text: "One CentHR API Logger row per request: method, endpoint, HTTP status, payload and response. Failed calls can be resynced up to 3 times." },
		{ title: "Alerts on failure", text: "Users in CentHr Settings > Error Alerts are notified when a sync fails." },
		{ title: "Migrates data in", text: "The Data Migration Tool pages records from one company's site into CentHR under the same company, across 15 sections." },
		{ title: "Runs HR processes locally", text: "Payroll runs, daily leave allocation and accrual, shift assignment, holiday lists and OTP-verified web forms." },
		{ title: "Cross-company roles", text: "Grants and removes User Permissions for managers who work across companies, on Employee update and delete." },
	],
	files: ["centhr/hooks.py", "centhr/api/common/target_client.py", "centhr/api/common/record_sync.py"],
}

export const PROCESSES: ProcessDef[] = [
	{
		key: "queue",
		label: "Job Queue",
		summary: "Every push runs as a background job, enqueued from a doc_event after the commit.",
		points: ["Queue: short", "Skipped while frappe.flags.centhr_migration is set, so migrated records are not sent back", "Redis lock per record avoids duplicate pushes"],
		files: ["centhr/api/common/record_sync.py (enqueue_job, sync_lock)"],
	},
	{
		key: "logger",
		label: "API Logger",
		summary: "CentHR API Logger keeps one row per HTTP request to a site.",
		points: ["status: Pending / Failed / Success", "request_method, endpoint, http_status", "request_payload, api_response, error", "resync() and resync_logs(), at most 3 attempts"],
		files: ["centhr/centhr/doctype/centhr_api_logger"],
	},
	{
		key: "migration",
		label: "Migration Tool",
		summary: "Centhr Data Migration Tool pulls records from a company's site, page by page (500 per page).",
		points: ["Runs on the long queue, with realtime progress", "Each run writes a Centhr Data Log with per-record results", "Can be stopped while it runs"],
		files: ["centhr/api/migrate/", "centhr/centhr/doctype/centhr_data_migration_tool", "centhr/centhr/doctype/centhr_data_log"],
	},
	{
		key: "scheduler",
		label: "Leave Scheduler",
		summary: "Daily jobs create Leave Allocations locally; each new allocation is then pushed by its own hook.",
		points: ["allocate_yearly_leaves", "accrue_annual_leave"],
		files: ["centhr/leave_policy/allocation.py"],
	},
]

export const MODULES: ModuleDef[] = [
	{
		key: "employees",
		label: "Employees",
		summary: "Employee and Department records are pushed to the company's site and kept in step on every change.",
		doctypes: ["Employee", "Department"],
		pushes: ["Employee", "Department"],
		hooks: ["insert", "update", "trash"],
		push: [
			"Employee: after_insert → POST, on_update → PUT, on_trash → DELETE",
			"Matched on the site by employee_number; a DELETE first clears linked records",
			"Site-required fields: department, company_email, territory, cost_center, channel",
			"Department: department_name, parent_department, company, is_group, disabled",
		],
		pull: ["Employee (migration section: employee)"],
		local: ["Cross-company role permissions on update and delete", "Salary Structure Assignment created from Employee fields"],
		notSynced: [],
		files: ["api/post/employee.py", "api/update/employee.py", "api/delete/employee.py", "api/department.py", "api/migrate/employee.py"],
	},
	{
		key: "attendance",
		label: "Attendance",
		summary: "Submitted Attendance is pushed as submitted; cancel and delete follow it to the site.",
		doctypes: ["Attendance", "Attendance Request", "Shift Type"],
		pushes: ["Attendance", "Shift Type"],
		hooks: ["insert", "update", "cancel", "trash"],
		push: [
			"Attendance: on_submit → POST (docstatus 1), on_cancel → PUT (docstatus 2), on_trash → DELETE",
			"Shift Type: insert / update / delete, to every site (same name on both sides)",
		],
		pull: ["Attendance (migration section: attendance)"],
		local: ["Attendance Request is OTP-verified and creates Attendance locally, which is then pushed"],
		notSynced: ["Attendance Request", "Shift Assignment", "Holiday List"],
		files: ["api/post/attendance.py", "api/delete/attendance.py", "api/post/shift_type.py", "api/web_form/attendance_request.py"],
	},
	{
		key: "leave",
		label: "Leave",
		summary: "Approved leave and every allocation change are pushed; leave setup is pulled in from the site.",
		doctypes: ["Leave Application", "Leave Allocation", "Leave Type", "Leave Policy", "Leave Policy Assignment"],
		pushes: ["Leave Application", "Leave Allocation"],
		hooks: ["insert", "update", "cancel", "trash"],
		push: [
			"Leave Application: on_submit → POST, on_cancel → PUT (docstatus 2), on_trash → DELETE",
			"Leave Allocation: insert, update, cancel, update after submit and delete",
		],
		pull: ["Leave Type", "Leave Policy", "Leave Policy Assignment", "Leave Allocation", "Leave Application"],
		local: ["Daily allocation and accrual by the leave policy scheduler", "OTP-verified leave web form"],
		notSynced: ["Leave Type, Leave Policy and Leave Policy Assignment are never pushed"],
		files: ["api/post/leave_application.py", "api/post/leave_allocation.py", "leave_policy/allocation.py"],
	},
	{
		key: "payroll",
		label: "Payroll",
		summary: "Payroll Entries are pushed and submitted on the site, which then creates its own Salary Slips.",
		doctypes: ["Payroll Entry", "Additional Salary", "Salary Slip"],
		pushes: ["Payroll Entry", "Additional Salary"],
		hooks: ["insert", "update", "cancel", "trash"],
		push: [
			"Payroll Entry: insert, update, cancel, update after submit and delete",
			"Matched by company, payroll_frequency, start_date, end_date, posting_date",
			"Additional Salary: matched by employee, salary_component, amount and payroll date",
		],
		pull: ["Payroll Entry", "Salary Slip", "Additional Salary"],
		local: ["Payroll runs (entry → slips → bank entry) are generated in CentHR"],
		notSynced: ["Salary Slip is never pushed; the site creates its own"],
		files: ["api/post/payroll_entry.py", "api/post/additional_salary.py", "api/payroll_run.py"],
	},
	{
		key: "salary",
		label: "Salary Structures",
		summary: "Structures, assignments and components are pushed after their dependencies are checked on the site.",
		doctypes: ["Salary Structure", "Salary Structure Assignment", "Salary Component"],
		pushes: ["Salary Structure", "Salary Structure Assignment", "Salary Component"],
		hooks: ["insert", "update", "cancel", "trash"],
		push: [
			"Salary Structure: GET checks each component on the site, then POST / PUT / DELETE",
			"Salary Structure Assignment: checks Employee and the submitted structure; matched by employee, structure, from_date",
			"Salary Component: insert / update / delete, to every site",
		],
		pull: ["Salary Component", "Salary Structure", "Salary Structure Assignment"],
		local: ["Bulk Salary Structure Assignment tool"],
		notSynced: [],
		files: ["api/post/salary_structure.py", "api/post/salary_structure_assignment.py", "api/post/salary_component.py"],
	},
	{
		key: "checkins",
		label: "Employee Check-ins",
		summary: "Check-ins are pushed to the site of the employee's company and mark Attendance in CentHR.",
		doctypes: ["Employee Checkin"],
		pushes: ["Employee Checkin"],
		hooks: ["insert", "update", "trash"],
		push: ["Employee Checkin: insert, update and delete, routed by the employee's company"],
		pull: [],
		local: ["OTP-verified check-in web form", "after_insert marks Attendance in CentHR, which is then pushed"],
		notSynced: ["No migration section"],
		files: ["api/post/employee_checkin.py", "api/employee_checkin_attendance.py"],
	},
]

export function buildGraph(sites: Site[]) {
	const nodes: GraphNode[] = [{ id: "core", kind: "core", label: CORE.label }]
	const edges: GraphEdge[] = []

	for (const process of PROCESSES) {
		const id = `process:${process.key}`
		nodes.push({ id, kind: "process", label: process.label, process })
		edges.push({ id: `core-${id}`, from: "core", to: id, kind: "internal", flow: 1, bend: 0.18, title: `CentHR ↔ ${process.label}`, detail: process.summary })
	}

	for (const site of sites) {
		const companyId = `company:${site.company}`
		nodes.push({ id: companyId, kind: "company", label: site.company, company: site.company, site })
		edges.push(
			{ id: `${companyId}-req`, from: "core", to: companyId, kind: "request", flow: 1, bend: 0.12, company: site.company, title: "API request", detail: `Pushes to ${site.host || "the site"} over /api/resource with token auth` },
			{ id: `${companyId}-res`, from: "core", to: companyId, kind: "response", flow: -1, bend: -0.12, company: site.company, title: "API response", detail: "HTTP status and body are written to CentHR API Logger" },
			{ id: `${companyId}-sync`, from: "core", to: companyId, kind: "sync", flow: -1, bend: 0.3, company: site.company, title: "Data migration", detail: "Data Migration Tool pulls records from this site in pages of 500" }
		)

		for (const module of MODULES) {
			const moduleId = `${companyId}/${module.key}`
			nodes.push({ id: moduleId, kind: "module", label: module.label, company: site.company, module })
			if (module.pushes.length) {
				edges.push({ id: `${moduleId}-push`, from: companyId, to: moduleId, kind: "request", flow: 1, bend: 0.16, company: site.company, title: `${module.label} · push`, detail: module.pushes.join(", ") })
			}
			if (module.pull.length) {
				edges.push({ id: `${moduleId}-pull`, from: companyId, to: moduleId, kind: "sync", flow: -1, bend: -0.16, company: site.company, title: `${module.label} · migration`, detail: module.pull.join(", ") })
			}
		}

		edges.push({ id: `${companyId}-checkin-attendance`, from: `${companyId}/checkins`, to: `${companyId}/attendance`, kind: "internal", flow: 1, bend: 0.25, company: site.company, title: "Check-in → Attendance", detail: "A new check-in marks Attendance in CentHR, which is then pushed" })
	}

	return { nodes, edges }
}

// ---- layered view: input → hidden → output ----------------------------------

export const HOOKS: ProcessDef[] = [
	{
		key: "insert",
		label: "after_insert",
		summary: "A new record is saved in CentHR. Its sync job is queued after the commit.",
		points: ["HTTP effect: POST to /api/resource/<DocType>", "Employee, Department, Leave Allocation, Employee Checkin, Shift Type, salary and payroll doctypes"],
		files: ["centhr/hooks.py (doc_events)"],
	},
	{
		key: "update",
		label: "on_update / on_submit",
		summary: "A record changes or is submitted. The record on the site is found and updated, or created if it is missing.",
		points: ["HTTP effect: PUT (upsert)", "Attendance and Leave Application sync on_submit: POST with docstatus 1", "on_update_after_submit for allocations, salary and payroll doctypes"],
		files: ["centhr/hooks.py (doc_events)", "centhr/api/update/"],
	},
	{
		key: "cancel",
		label: "on_cancel",
		summary: "A submitted record is cancelled in CentHR and cancelled on the site too.",
		points: ["HTTP effect: PUT with docstatus 2", "Attendance, Leave Application, Leave Allocation, Salary Structure (+ Assignment), Additional Salary, Payroll Entry"],
		files: ["centhr/hooks.py (doc_events)"],
	},
	{
		key: "trash",
		label: "on_trash",
		summary: "A record is deleted in CentHR and deleted on the site.",
		points: ["HTTP effect: DELETE", "Employee delete first clears records linked to it on the site"],
		files: ["centhr/hooks.py (doc_events)", "centhr/api/delete/"],
	},
]

export const ENGINE: ProcessDef[] = [
	PROCESSES[0],
	{
		key: "router",
		label: "Router",
		summary: "get_targets(company) picks the site for the record from CentHr Settings > Authorization.",
		points: ["Matches the record's company (or its employee's company)", "Shift Type and Salary Component have no company, so they go once to every site"],
		files: ["centhr/api/common/record_sync.py (get_targets)", "centhr/api/post/*.py (get_targets)"],
	},
	{
		key: "client",
		label: "API Client",
		summary: "Sends the REST call to the site and records the result.",
		points: ["Authorization: token api_key:api_secret", "Timeout (10, 30) s, 2 retries", "GET checks first (existing record, linked Employee, components)"],
		files: ["centhr/api/common/target_client.py (TargetClient)"],
	},
	PROCESSES[1],
	PROCESSES[2],
]

export const LAYER_COLUMNS = [
	{ title: "Input · CentHR modules", caption: "Records created and approved in CentHR" },
	{ title: "Hidden · Event hooks", caption: "Frappe doc_events fire on each change" },
	{ title: "Hidden · Sync engine", caption: "A background job routes and sends the call" },
	{ title: "Output · Company sites", caption: "Each company's own HRMS site" },
]

export function buildLayeredGraph(sites: Site[]) {
	const nodes: GraphNode[] = []
	const edges: GraphEdge[] = []
	const internal = (from: string, to: string, title: string, detail: string, bend = 0.06): GraphEdge => ({ id: `${from}>${to}`, from, to, kind: "internal", flow: 1, bend, title, detail })

	for (const module of MODULES) nodes.push({ id: `module:${module.key}`, kind: "module", label: module.label, module, layer: 0, size: 8 })
	for (const hook of HOOKS) nodes.push({ id: `hook:${hook.key}`, kind: "process", label: hook.label, process: hook, layer: 1, size: 8.5 })
	for (const engine of ENGINE) nodes.push({ id: `process:${engine.key}`, kind: "process", label: engine.label, process: engine, layer: 2, size: 9 })
	for (const site of sites) nodes.push({ id: `company:${site.company}`, kind: "company", label: site.company, company: site.company, site, layer: 3 })

	for (const module of MODULES) {
		for (const key of module.hooks) {
			const hook = HOOKS.find((h) => h.key === key)!
			edges.push(internal(`module:${module.key}`, `hook:${key}`, `${module.label} → ${hook.label}`, module.pushes.join(", ")))
		}
		if (module.pull.length) {
			edges.push({ id: `migration>${module.key}`, from: "process:migration", to: `module:${module.key}`, kind: "sync", flow: 1, bend: -0.3, title: `Migration → ${module.label}`, detail: module.pull.join(", ") })
		}
	}
	for (const hook of HOOKS) edges.push(internal(`hook:${hook.key}`, "process:queue", `${hook.label} → Job Queue`, "Enqueued on the short queue after the commit"))
	edges.push(internal("process:queue", "process:router", "Job Queue → Router", "The job looks up the target site", 0.3))
	edges.push(internal("process:router", "process:client", "Router → API Client", "One call per matching Authorization row", 0.3))

	for (const site of sites) {
		const id = `company:${site.company}`
		edges.push(
			{ id: `client>${id}`, from: "process:client", to: id, kind: "request", flow: 1, bend: 0.05, company: site.company, title: `API request → ${site.company}`, detail: "POST / PUT / DELETE on /api/resource/<DocType>" },
			{ id: `${id}>logger`, from: id, to: "process:logger", kind: "response", flow: 1, bend: 0.05, company: site.company, title: `API response ← ${site.company}`, detail: "Status, HTTP code and body saved to CentHR API Logger" },
			{ id: `${id}>migration`, from: id, to: "process:migration", kind: "sync", flow: 1, bend: -0.08, company: site.company, title: `Data migration ← ${site.company}`, detail: "Pulled on demand by the Data Migration Tool, 500 records per page" }
		)
	}

	return { nodes, edges, columns: LAYER_COLUMNS }
}
