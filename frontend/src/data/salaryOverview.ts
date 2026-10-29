import type { Column } from "@/components/DataTable.vue"
import { api } from "@/data/api"
import { formatCurrency, formatDateShort } from "@/utils/format"
import type { Tone } from "@/utils/status"

/** One employee of the company in the payroll period, from centhr.api.salary_overview.get_salary_overview. */
export interface SalaryRow {
	name: string
	employee_name: string
	department: string | null
	designation: string | null
	status: string
	date_of_joining: string | null
	relieving_date: string | null
	assignment: string | null
	salary_structure: string | null
	structure_inactive: boolean
	base: number | null
	currency: string | null
	effective_from: string | null
	salary_slip: string | null
	slip_status: string | null
	gross_pay: number | null
	total_deduction: number | null
	net_pay: number | null
}

export interface Period {
	from: string
	to: string
}

interface RowFilter {
	key: string
	label: string
	test: (row: SalaryRow, period: Period) => boolean
}

export interface Tile extends RowFilter {
	tone?: Tone
}

export function getSalaryOverview(company: string, period: Period) {
	return api<SalaryRow[]>("centhr.api.salary_overview.get_salary_overview", {
		company,
		from_date: period.from,
		to_date: period.to,
	})
}

/** The stat tiles; each one also filters the table. */
export const TILES: Tile[] = [
	{ key: "active", label: "Total active", test: (r) => r.status === "Active" },
	{ key: "submitted", label: "Submitted", tone: "green", test: (r) => r.slip_status === "Submitted" },
	{ key: "draft", label: "Draft", tone: "amber", test: (r) => r.slip_status === "Draft" },
	{ key: "pending", label: "Pending", tone: "red", test: (r) => r.status === "Active" && !r.salary_slip },
	{ key: "joined", label: "Joined this period", tone: "blue", test: (r, p) => inPeriod(r.date_of_joining, p) },
	{ key: "exited", label: "Exited this period", tone: "gray", test: (r, p) => inPeriod(r.relieving_date, p) },
]

/** The structure chips above the table. */
export const STRUCTURE_VIEWS: RowFilter[] = [
	{ key: "all", label: "All", test: () => true },
	{ key: "missing", label: "Missing structure", test: (r) => !r.assignment },
	{ key: "assigned", label: "Assigned", test: (r) => !!r.assignment },
	{ key: "inactive", label: "Inactive structure", test: (r) => r.structure_inactive },
]

/** Table columns the overview pages pick from; SalaryOverviewView renders the special cells. */
export const COLUMNS = {
	name: { key: "name", label: "Employee ID", width: "110px", sortable: true },
	employee_name: { key: "employee_name", label: "Employee name", width: "minmax(180px,1.8fr)", sortable: true, class: "font-medium" },
	department: { key: "department", label: "Department", width: "minmax(130px,1.2fr)", sortable: true, hideOnMobile: true },
	designation: { key: "designation", label: "Designation", width: "minmax(130px,1.2fr)", sortable: true, hideOnMobile: true },
	salary_structure: { key: "salary_structure", label: "Current structure", width: "minmax(170px,1.6fr)", sortable: true },
	base: money("base", "Base salary"),
	gross_pay: money("gross_pay", "Gross pay"),
	total_deduction: money("total_deduction", "Deductions"),
	net_pay: money("net_pay", "Net pay"),
	effective_from: { key: "effective_from", label: "Effective since", width: "110px", sortable: true, format: (v) => formatDateShort(v) },
	slip_status: { key: "slip_status", label: "Payroll status", width: "110px", sortable: true },
	actions: { key: "actions", label: "", width: "160px", align: "right" },
} satisfies Record<string, Column>

export function countBy(filters: RowFilter[], rows: SalaryRow[], period: Period): Record<string, number> {
	return Object.fromEntries(filters.map((f) => [f.key, rows.filter((r) => f.test(r, period)).length]))
}

/** Sorted, distinct non-empty values of one column, for the filter dropdowns. */
export function distinct(rows: SalaryRow[], key: keyof SalaryRow): string[] {
	return [...new Set(rows.map((r) => r[key]).filter(Boolean) as string[])].sort()
}

export function compareRows(a: SalaryRow, b: SalaryRow, key: string): number {
	const x = a[key as keyof SalaryRow] ?? ""
	const y = b[key as keyof SalaryRow] ?? ""
	return typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y))
}

/** A right-aligned amount in the row's currency. */
function money(key: string, label: string): Column {
	return { key, label, width: "130px", align: "right", sortable: true, format: (v, r) => formatCurrency(v, r.currency) }
}

function inPeriod(date: string | null, period: Period): boolean {
	return !!date && period.from <= date && date <= period.to
}
