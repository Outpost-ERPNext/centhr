import { ref, watch, type InjectionKey, type Ref } from "vue"
import { api, downloadFile } from "@/data/api"
import type { PayrollRun } from "@/data/payrollRun"
import type { SalaryRow } from "@/data/salaryOverview"
import type { Tone } from "@/utils/status"

export const METHOD = "centhr.payroll_dashboard.api"

/** The company (empty for all) and pay cycle every tab works on. */
export interface Scope {
	company: string
	from: string
	to: string
}

/** Opens an employee's quick view; the dashboard provides it to its tabs. */
export const OPEN_EMPLOYEE: InjectionKey<(employee: string) => void> = Symbol("openEmployee")

export const TABS = [
	{ key: "audit", label: "Pre-Check Audit" },
	{ key: "employees", label: "Employees" },
	{ key: "attendance", label: "Attendance" },
	{ key: "processing", label: "Payroll Processing" },
	{ key: "analytics", label: "Analytics" },
	{ key: "advances", label: "Advances & Deductions" },
	{ key: "reports", label: "Reports" },
	{ key: "compliance", label: "Compliance" },
] as const
export type TabKey = (typeof TABS)[number]["key"]

export interface AuditCard {
	key: string
	label: string
	count: number
	info?: boolean
}
export interface AuditRow extends SalaryRow {
	issues: Record<string, string>
	hold: string | null
	hold_reason: string | null
	hold_to?: string
	hold_cycles?: number
	/** Held for as long as HRMS allows, so until someone releases it. */
	hold_until_released?: boolean
	hold_by?: string
	/** When the last reminder of the cycle about this employee went out. */
	reminded_on: string | null
	attendance: AttendanceCounts
}
export interface AttendanceCounts {
	working_days: number
	present: number
	work_from_home: number
	half_day: number
	paid_leave: number
	unpaid_leave: number
	absent: number
	unmarked: number
	/** Days without attendance in an open leave application or a draft attendance request. */
	pending_leave: number
	pending_request: number
	holidays: number
	paid_days: number
}
export interface Slip {
	name: string
	employee: string
	employee_name: string
	department: string | null
	status: string
	docstatus: number
	payroll_entry: string | null
	currency: string
	total_working_days: number
	payment_days: number
	absent_days: number
	leave_without_pay: number
	gross_pay: number
	total_deduction: number
	net_pay: number
	mode_of_payment: string | null
	bank_name: string | null
	bank_account_no: string | null
	/** Deducted to recover employee advances (IOUs). */
	iou_deduction: number
}
export interface Totals {
	headcount: number
	gross_pay: number
	total_deduction: number
	net_pay: number
}
export interface Obligation {
	name: string
	obligation_name: string
	company: string
	frequency: string
	liability_account: string
	payment_account: string | null
	payable: number
	remitted: number
	balance: number
	accruals: Voucher[]
	payments: Voucher[]
	deadline: string
	status: string
	requests: PaymentRequest[]
	/** A request that still waits to be approved or paid; a new one cannot be made meanwhile. */
	open_request: string | null
}
export interface Voucher {
	voucher_type: string
	voucher_no: string
	date: string
	amount: number
}
/** A Payment Request Form: Accounts approves it before the bank entry is made. */
export interface PaymentRequest {
	name: string
	status: "Pending Approval" | "Approved" | "Rejected" | "Paid"
	amount: number
	currency: string | null
	payment_account: string | null
	journal_entry: string | null
	requested_by_name: string | null
	approved_by_name: string | null
	approved_on: string | null
	rejection_reason: string | null
	creation: string
	/** The user may approve or reject it now. */
	can_decide: boolean
}
export const REQUEST_TONES: Record<PaymentRequest["status"], Tone> = {
	"Pending Approval": "amber",
	Approved: "blue",
	Rejected: "red",
	Paid: "green",
}
export interface ObligationBreakdown {
	obligation_name: string
	components: string[]
	rows: { employee: string; employee_name: string; department: string | null; salary_slip: string; currency: string; components: Record<string, number>; amount: number }[]
	total: number
	payable: number
	/** Booked to the liability account without a salary slip. */
	difference: number
}
export interface PayoutList {
	payroll_entry: string
	rows: { name: string; employee: string; employee_name: string; department: string | null; status: string; currency: string; net_pay: number; paid_by: string | null; bank_name: string | null; bank_account_no: string | null; missing_account: boolean }[]
	total: number
	missing_accounts: number
}

export const args = (scope: Scope) => ({ company: scope.company || undefined, from_date: scope.from, to_date: scope.to })

export interface BulkResult {
	done: string[]
	failed: { name: string; error: string }[]
}
export const getAudit = (scope: Scope) =>
	api<{ cards: AuditCard[]; rows: AuditRow[]; auto_attendance: boolean }>(`${METHOD}.get_audit`, args(scope))
/** `cycles` pay cycles from this one on; 0 holds the salary until it is released. */
export const setHold = (employee: string, scope: Scope, reason: string, cycles = 1) =>
	api<string>(`${METHOD}.set_payroll_hold`, { employee, from_date: scope.from, to_date: scope.to, reason, cycles })
export const releaseHold = (withholding: string) => api(`${METHOD}.release_payroll_hold`, { withholding })
export const releaseHolds = (withholdings: string[]) => api<BulkResult>(`${METHOD}.release_payroll_holds`, { withholdings })
export const deleteNegativeSlips = (scope: Scope) => api<BulkResult>(`${METHOD}.delete_negative_salary_slips`, args(scope))
export const markAutoAttendance = (scope: Scope) =>
	api<{ employees: number; created: number; skipped: number }>(`${METHOD}.mark_auto_attendance`, args(scope))
/** Without `employees`, everyone in the cycle with something open. */
export const sendReminders = (scope: Scope, employees?: string[]) =>
	api<{ sent: number; recipients: string[] }>(`${METHOD}.send_payroll_reminders`, { ...args(scope), employees })
export const getPayoutList = (payrollEntry: string) => api<PayoutList>(`${METHOD}.get_payout_list`, { payroll_entry: payrollEntry })
export const exportPayoutList = (payrollEntry: string) => downloadFile(`${METHOD}.export_payout_list`, { payroll_entry: payrollEntry })
export const decidePaymentRequest = (name: string, approve: boolean, reason?: string) =>
	api<{ name: string; status: string }>(`${METHOD}.decide_payment_request`, { name, approve: approve ? 1 : 0, reason })
export const getObligationBreakdown = (obligation: string, scope: Scope) =>
	api<ObligationBreakdown>(`${METHOD}.get_obligation_breakdown`, { obligation, from_date: scope.from, to_date: scope.to })
export const exportObligationBreakdown = (obligation: string, scope: Scope) =>
	downloadFile(`${METHOD}.export_obligation_breakdown`, { obligation, from_date: scope.from, to_date: scope.to })
export const getAttendance = (scope: Scope) =>
	api<(AttendanceCounts & Record<string, any>)[]>(`${METHOD}.get_attendance`, args(scope))
export const getProcessing = (scope: Scope) =>
	api<{ totals: Totals; previous: Totals; runs: PayrollRun[]; slips: Slip[]; confidential_batches: Record<string, string> }>(
		`${METHOD}.get_processing`,
		args(scope)
	)
export const updateSlips = (action: "submit" | "recalculate" | "delete", names: string[]) =>
	api<BulkResult>(`${METHOD}.update_salary_slips`, { action, names })
export const getAnalytics = (view: string, scope: Scope) => api<Record<string, any>>(`${METHOD}.get_analytics`, { view, ...args(scope) })
export const getAdvances = (scope: Scope) =>
	api<{ advances: Record<string, any>[]; deductions: Record<string, any>[]; auto_recovery: boolean }>(`${METHOD}.get_advances`, args(scope))
export const recoverOverdueAdvances = (scope: Scope) =>
	api<number>(`${METHOD}.recover_overdue_advances`, { company: scope.company, to_date: scope.to })
export const recoverAdvance = (advance: string, salaryComponent: string, payrollDate: string) =>
	api<string>(`${METHOD}.recover_advance`, { advance, salary_component: salaryComponent, payroll_date: payrollDate })
export const getReports = () => api<Record<string, any>[]>(`${METHOD}.get_reports`)
export const getCompliance = (scope: Scope) =>
	api<{ obligations: Obligation[]; no_access?: boolean }>(`${METHOD}.get_compliance`, args(scope))
export const requestObligationPayment = (obligation: string, amount: number, paymentAccount?: string | null) =>
	api<string>(`${METHOD}.request_obligation_payment`, { obligation, amount, payment_account: paymentAccount || undefined })

// Settings of the chosen company

export interface PayrollSettings {
	company: string
	/** Day of the month the pay cycle starts; 1 means calendar months (or the company's Payroll Period). */
	start_day: number
	auto_recover_advances: 0 | 1
	recovery_component: string | null
	can_edit: boolean
	frequency: string
	site: SiteSettings
}
/** The calculation rules of HRMS's Payroll Settings; they apply to every company of the site. */
export interface SiteSettings {
	payroll_based_on: "Leave" | "Attendance"
	include_holidays_in_total_working_days: 0 | 1
	consider_unmarked_attendance_as: "Present" | "Absent"
	process_payroll_accounting_entry_based_on_employee: 0 | 1
}
export const getPayrollSettings = (company: string) => api<PayrollSettings>(`${METHOD}.get_payroll_settings`, { company })
export const savePayrollSettings = (company: string, startDay: number, autoRecover: boolean, site?: SiteSettings) =>
	api<PayrollSettings>(`${METHOD}.save_payroll_settings`, { company, start_day: startDay, auto_recover_advances: autoRecover ? 1 : 0, site })

// Salary slip quick view

export interface SlipDetails extends Slip {
	designation: string | null
	company: string
	start_date: string
	end_date: string
	salary_structure: string | null
	journal_entry: string | null
	bank_name: string | null
	bank_account_no: string | null
	earnings: { salary_component: string; amount: number }[]
	deductions: { salary_component: string; amount: number }[]
	/** The salary component that recovers advances; its deduction is shown apart. */
	iou_component: string | null
}
export const getSlipDetails = (name: string) => api<SlipDetails>(`${METHOD}.get_salary_slip_details`, { name })

/** The cycle's salary slips as an Excel file, in the shared overview export. */
export const exportSlips = (scope: Scope, employees: string[]) =>
	downloadFile("centhr.api.salary_overview.export_salary_overview", { ...args(scope), employees })

/**
 * Data of one tab, loaded for the scope and reloaded when the company or cycle changes.
 * A slower, older response never replaces a newer one.
 */
export function useTabData<T>(scope: Scope, load: (scope: Scope) => Promise<T>) {
	const data = ref<T | null>(null) as Ref<T | null>
	const loading = ref(false)
	const error = ref<string | null>(null)
	let requestId = 0

	async function reload() {
		if (!scope.from || !scope.to) return
		const id = ++requestId
		loading.value = true
		error.value = null
		try {
			const result = await load({ ...scope })
			if (id === requestId) data.value = result
		} catch (e: any) {
			if (id === requestId) error.value = e?.messages?.[0] || e?.message || "Could not load this tab"
		} finally {
			if (id === requestId) loading.value = false
		}
	}

	watch(() => [scope.company, scope.from, scope.to], reload, { immediate: true })
	return { data, loading, error, reload }
}

/** "+12.5%" against the previous cycle, or null when there is nothing to compare. */
export function change(now: number, before: number): number | null {
	return before ? ((now - before) / before) * 100 : null
}

// Employee advance quick view

export interface AdvanceDetails {
	name: string
	employee: string
	employee_name: string
	department: string | null
	company: string
	status: string
	docstatus: number
	posting_date: string
	due_date: string | null
	purpose: string | null
	purpose_type: string | null
	currency: string
	advance_amount: number
	paid_amount: number
	claimed_amount: number
	return_amount: number
	outstanding_amount: number
	repay_unclaimed_amount_from_salary: 0 | 1
	recovery_scheduled: boolean
	deductions: { name: string; salary_component: string; amount: number; payroll_date: string; docstatus: number; salary_slip: string | null }[]
	claims: { parent: string; allocated_amount: number; docstatus: number }[]
	due_status: "Overdue" | "Due this cycle" | "Upcoming" | "No due date"
	/** Why the advance is, or is not, taken off a salary in the cycle. */
	recovery_note: string
}
/** With a pay cycle, also where the advance's recovery stands in it. */
export const getAdvanceDetails = (name: string, scope?: Scope) =>
	api<AdvanceDetails>(`${METHOD}.get_advance_details`, { name, from_date: scope?.from || undefined, to_date: scope?.to || undefined })
