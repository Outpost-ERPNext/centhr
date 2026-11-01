import { inPeriod, type Period, type SalaryRow } from "@/data/salaryOverview"
import type { Tone } from "@/utils/status"

export type Severity = "error" | "warning" | "info"

export interface AuditCheck {
	key: string
	label: string
	/** What it means for the payroll run, shown under the label. */
	hint: string
	severity: Severity
	test: (row: SalaryRow, period: Period) => boolean
}

export const SEVERITY_TONE: Record<Severity, Tone> = { error: "red", warning: "amber", info: "blue" }

/** Checks to clear before generating and submitting payroll; errors stop employees from being paid correctly. */
export const AUDIT_CHECKS: AuditCheck[] = [
	{
		key: "missing_structure",
		label: "No salary structure",
		hint: "Active employees without a submitted assignment get no salary slip.",
		severity: "error",
		test: (r) => r.status === "Active" && !r.assignment,
	},
	{
		key: "inactive_structure",
		label: "Inactive salary structure",
		hint: "Payroll skips employees whose structure is inactive.",
		severity: "error",
		test: (r) => r.structure_inactive,
	},
	{
		key: "zero_base",
		label: "Zero base salary",
		hint: "The assignment has no base, so formula components come out as zero.",
		severity: "warning",
		test: (r) => !!r.assignment && !r.base,
	},
	{
		key: "non_positive_net",
		label: "Net pay zero or negative",
		hint: "Deductions are equal to or more than earnings on the salary slip.",
		severity: "error",
		test: (r) => !!r.salary_slip && (r.net_pay ?? 0) <= 0,
	},
	{
		key: "missing_bank",
		label: "No bank account",
		hint: "Paid by bank, but the employee has no bank account number.",
		severity: "warning",
		test: (r) => r.salary_mode === "Bank" && !r.bank_ac_no,
	},
	{
		key: "draft_slip",
		label: "Salary slip still in draft",
		hint: "Draft slips are not booked or paid until they are submitted.",
		severity: "warning",
		test: (r) => r.slip_status === "Draft",
	},
	{
		key: "joined",
		label: "Joined in this period",
		hint: "Check that pay is pro-rated from the joining date.",
		severity: "info",
		test: (r, p) => inPeriod(r.date_of_joining, p),
	},
	{
		key: "exited",
		label: "Left in this period",
		hint: "Check the final settlement: pro-rated pay, leave encashment and recoveries.",
		severity: "info",
		test: (r, p) => inPeriod(r.relieving_date, p),
	},
]

export interface AuditResult extends AuditCheck {
	rows: SalaryRow[]
}

/** The checks that found employees, worst first. */
export function runAudit(rows: SalaryRow[], period: Period): AuditResult[] {
	const order: Severity[] = ["error", "warning", "info"]
	return AUDIT_CHECKS.map((check) => ({ ...check, rows: rows.filter((r) => check.test(r, period)) }))
		.filter((result) => result.rows.length)
		.sort((a, b) => order.indexOf(a.severity) - order.indexOf(b.severity))
}
