import { api, downloadFile } from "@/data/api"

export type IOUCategory =
	| "IOU Application"
	| "IOU Claim Settlement – No Linked IOU"
	| "IOU Claim Settlement – Linked IOU"

export interface IOUApproverInfo {
	user?: string | null
	name?: string | null
	status: "Approved" | "Pending" | "Rejected" | "Not Required"
	datetime?: string | null
	reason?: string | null
}

export type IOUDoctype = "IOU and Loans" | "Employee Advance" | "Expense Claim"

/** What the current user can do with a record (worked out on the server, SOP approval steps) */
export type IOUAction = "Approve" | "Reject" | "Modify" | "Pay"

export interface IOURow {
	doctype: IOUDoctype
	name: string
	category: IOUCategory
	advance_type: IOUCategory
	employee: string
	employee_name: string
	department?: string | null
	company?: string | null
	amount: number
	outstanding_amount?: number
	paid_amount?: number
	claimed_amount?: number
	posting_date: string
	due_date?: string | null
	status: string
	is_closed: boolean
	is_overdue: boolean
	is_pending_approval: boolean
	purpose?: string | null
	employee_advance?: string | null
	linked_iou?: string | null
	approvers: {
		hod: IOUApproverInfo
		finance_1: IOUApproverInfo
		finance_2: IOUApproverInfo
	}
	claim_method?: string | null
	repay_from_salary?: number
	purpose_type?: string | null
	current_approver?: string | null
	rejection_reason?: string | null
	/** Claims: the part that settles the IOU, and the part paid to the employee */
	amount_from_iou?: number
	amount_from_pocket?: number
	actions?: IOUAction[]
	creation?: string
}

export interface IOUCategoryStat {
	count: number
	amount: number
}

export interface IOUStats {
	iou_application: IOUCategoryStat
	settlement_no_link: IOUCategoryStat
	settlement_linked: IOUCategoryStat
	total: IOUCategoryStat
	advances: IOUCategoryStat
	pending_approval: IOUCategoryStat
	overdue: IOUCategoryStat
	waiting_for_me: IOUCategoryStat
}

/** Drill-down of the top cards */
export type IOUFocus = "advances" | "pending" | "overdue" | "mine"

export interface IOUFilters {
	employee?: string
	company?: string
	advance_type?: string
	status?: string
	closed?: number
	category?: string
	focus?: IOUFocus
	search?: string
}

export interface IOUExpenseItem {
	name?: string
	/** IOU and Loans rows */
	expense_claim_type?: string
	/** Expense Claim rows */
	expense_type?: string
	description?: string
	amount: number
	cost_center?: string
	department?: string
	channel?: string
	attachment?: string
	attachment_2?: string
	attachment_3?: string
}

const METHOD = "centhr.api.iou"

export function getIOUDashboard(filters: IOUFilters = {}) {
	return api<{
		records: IOURow[]
		stats: IOUStats
		advance_types: IOUCategory[]
		statuses: string[]
	}>(`${METHOD}.get_iou_dashboard_data`, filters)
}

export function getIOUDetail(name: string, doctype = "IOU and Loans") {
	return api<Record<string, any>>(`${METHOD}.get_iou_detail`, { name, doctype })
}

export function exportIOURecords(filters: IOUFilters = {}, names?: string[]) {
	return downloadFile(`${METHOD}.export_iou_records`, { ...filters, names })
}

export interface IOUActionArgs {
	reason?: string
	advance_amount?: number
	expenses?: { name: string; expense_type?: string; amount?: number }[]
}

export function applyIOUAction(doctype: IOUDoctype, name: string, action: Exclude<IOUAction, "Pay">, args: IOUActionArgs = {}) {
	return api<Record<string, any>>(`${METHOD}.apply_iou_action`, { doctype, name, action, ...args })
}

export function payIOU(
	doctype: IOUDoctype,
	name: string,
	args: { bank_account: string; reference_no?: string; payment_advice?: string }
) {
	return api<{ payment_entry: string; detail: Record<string, any> }>(`${METHOD}.pay_iou`, { doctype, name, ...args })
}

export interface PaymentAccount {
	name: string
	account_name: string
	account_type: "Bank" | "Cash"
	account_currency?: string
}

export function getPaymentAccounts(company: string) {
	return api<PaymentAccount[]>(`${METHOD}.get_payment_accounts`, { company })
}

export function getExpenseClaimTypes() {
	return api<string[]>(`${METHOD}.get_expense_claim_types`)
}
