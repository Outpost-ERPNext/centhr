import { ref, watch, type Ref } from "vue"
import { api, downloadFile } from "@/data/api"
import type { PayrollRun } from "@/data/payrollRun"
import type { SalaryRow } from "@/data/salaryOverview"

const METHOD = "centhr.payroll_dashboard.api"

/** The company (empty for all) and pay cycle every tab works on. */
export interface Scope {
	company: string
	from: string
	to: string
}

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
	accruals: string[]
	payments: { voucher_no: string; amount: number; date: string }[]
	deadline: string
	status: string
	open_requests: string[]
}

const args = (scope: Scope) => ({ company: scope.company || undefined, from_date: scope.from, to_date: scope.to })

export const getAudit = (scope: Scope) => api<{ cards: AuditCard[]; rows: AuditRow[] }>(`${METHOD}.get_audit`, args(scope))
export const setHold = (employee: string, scope: Scope) => api<string>(`${METHOD}.set_payroll_hold`, { employee, ...args(scope) })
export const releaseHold = (withholding: string) => api(`${METHOD}.release_payroll_hold`, { withholding })
export const getAttendance = (scope: Scope) =>
	api<(AttendanceCounts & Record<string, any>)[]>(`${METHOD}.get_attendance`, args(scope))
export const getProcessing = (scope: Scope) =>
	api<{ totals: Totals; previous: Totals; runs: PayrollRun[]; slips: Slip[] }>(`${METHOD}.get_processing`, args(scope))
export const updateSlips = (action: "submit" | "recalculate" | "delete", names: string[]) =>
	api<{ done: string[]; failed: { name: string; error: string }[] }>(`${METHOD}.update_salary_slips`, { action, names })
export const getAnalytics = (view: string, scope: Scope) => api<Record<string, any>>(`${METHOD}.get_analytics`, { view, ...args(scope) })
export const getAdvances = (scope: Scope) =>
	api<{ advances: Record<string, any>[]; deductions: Record<string, any>[] }>(`${METHOD}.get_advances`, args(scope))
export const recoverAdvance = (advance: string, salaryComponent: string, payrollDate: string) =>
	api<string>(`${METHOD}.recover_advance`, { advance, salary_component: salaryComponent, payroll_date: payrollDate })
export const getReports = () => api<Record<string, any>[]>(`${METHOD}.get_reports`)
export const getCompliance = (scope: Scope) =>
	api<{ obligations: Obligation[]; no_access?: boolean }>(`${METHOD}.get_compliance`, args(scope))
export const requestObligationPayment = (obligation: string, amount: number, paymentAccount?: string | null) =>
	api<string>(`${METHOD}.request_obligation_payment`, { obligation, amount, payment_account: paymentAccount || undefined })

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
