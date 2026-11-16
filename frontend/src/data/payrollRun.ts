import { api } from "@/data/api"

/** A Payroll Entry and the step it waits for, from centhr.api.payroll. */
export interface PayrollRun {
	name: string
	company: string
	/** Regular, or Exited for employees who left in the cycle. */
	batch: PayrollBatch
	status: string
	docstatus: number
	number_of_employees: number
	salary_slips_created: number
	salary_slips_submitted: number
	payment_account: string | null
	error_message: string | null
	payouts: { name: string; docstatus: number }[]
	has_withheld_salaries: boolean
	next_step: StepKey | null
}

export type PayrollBatch = "Regular" | "Exited"

export type StepKey = "submit" | "create_slips" | "submit_slips" | "bank_entry" | "release_withheld" | "cancel"

interface Step {
	label: string
	icon: string
	confirm: string
	/** Pays out of a bank or cash account the user picks. */
	needsAccount?: boolean
	danger?: boolean
}

export const STEPS: Record<StepKey, Step> = {
	submit: {
		label: "Submit payroll",
		icon: "lucide-play",
		confirm: "Submit this payroll entry? Draft salary slips are created for its employees.",
	},
	create_slips: {
		label: "Create salary slips",
		icon: "lucide-refresh-cw",
		confirm: "Create the salary slips of this payroll entry again?",
	},
	submit_slips: {
		label: "Submit salary slips",
		icon: "lucide-send",
		confirm: "Submit all draft salary slips? This books the payroll accrual and the slips can no longer be edited.",
	},
	bank_entry: {
		label: "Request payment",
		icon: "lucide-landmark",
		confirm: "Request payment of these salaries? A draft bank entry is created for Finance to review and submit in Accounts.",
		needsAccount: true,
	},
	release_withheld: {
		label: "Release withheld salaries",
		icon: "lucide-hand-coins",
		confirm: "Create the bank entry for the withheld salaries?",
		needsAccount: true,
	},
	cancel: {
		label: "Cancel payroll",
		icon: "lucide-ban",
		confirm: "Cancel this payroll entry? Its salary slips are deleted and its journal entries are cancelled.",
		danger: true,
	},
}

/** The three stages shown on a run, in order. */
export function stages(run: PayrollRun) {
	return [
		{ label: "Salary slips created", done: !!run.salary_slips_created },
		{ label: "Salary slips submitted", done: !!run.salary_slips_submitted },
		{ label: "Payment requested", done: run.payouts.length > 0 },
	]
}

/** Where the payment of a run stands, once it was requested: the bank entry is a draft until Finance submits it. */
export function paymentStatus(run: PayrollRun): { label: string; tone: "amber" | "green" } | null {
	if (!run.payouts.length) return null
	return run.payouts.every((entry) => entry.docstatus === 1)
		? { label: "Paid", tone: "green" }
		: { label: "Payment requested", tone: "amber" }
}

/** Without a company, every company's runs in the period. */
export function getPayrollRuns(company: string, from: string, to: string) {
	return api<PayrollRun[]>("centhr.api.payroll.get_payroll_runs", { company, start_date: from, end_date: to })
}

export function generatePayroll(company: string, from: string, to: string, batch: PayrollBatch) {
	return api<PayrollRun & { advances_recovered: number }>("centhr.api.payroll.generate_payroll", {
		company,
		start_date: from,
		end_date: to,
		batch,
	})
}

export function runPayrollStep(name: string, step: StepKey, paymentAccount?: string | null) {
	return api<PayrollRun>("centhr.api.payroll.run_payroll_step", {
		payroll_entry: name,
		step,
		payment_account: paymentAccount || undefined,
	})
}
