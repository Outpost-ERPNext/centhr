import { api, downloadFile, serverMessage } from "@/data/api"
import { METHOD, args, type Scope } from "@/data/payrollDashboard"
import type { Tone } from "@/utils/status"

/** Finance's master payroll sheet of a pay cycle, and how it compares with the cycle's salary slips. */

export type ReconcileStatus = "Matched" | "Discrepancy" | "Missing in Excel" | "Missing in ERP"
export const RECONCILE_STATUSES: ReconcileStatus[] = ["Discrepancy", "Matched", "Missing in ERP", "Missing in Excel"]
export const RECONCILE_TONES: Record<ReconcileStatus, Tone> = {
	Matched: "green",
	Discrepancy: "red",
	"Missing in Excel": "amber",
	"Missing in ERP": "amber",
}

/** A salary component of the slip beside its column of the sheet. */
export interface ComponentLine {
	component: string
	type: "Earning" | "Deduction"
	erp: number
	/** Header of the sheet's column, or null while the component is not mapped. */
	column: string | null
	excel: number | null
	variance: number | null
	differs: boolean
}
export interface ReconcileRow {
	employee: string
	employee_name: string | null
	department: string | null
	salary_slip: string | null
	currency: string | null
	status: ReconcileStatus
	differences: string[]
	remarks: string[]
	components: ComponentLine[]
	variance: number | null
	erp_net_pay: number | null
	excel_net_pay: number | null
	erp_payment_days: number | null
	excel_payment_days: number | null
}
export interface StoredSheet {
	file_name: string
	file_url: string
	file_size: number | null
	uploaded_on: string
	uploaded_by: string
}
export interface Reconciliation {
	/** Null until a sheet is uploaded for the cycle; the other fields come with a sheet. */
	sheet: StoredSheet | null
	/** Why the sheet cannot be compared yet, such as a column that still has to be mapped. */
	problem?: string | null
	rows?: ReconcileRow[]
	summary?: Record<ReconcileStatus | "excel" | "slips", number>
	/** Rows of the sheet that have no net pay, so were not compared. */
	ignored?: number
}

/** Something CentHR compares, which a column of the sheet can be mapped to. */
export interface MappingTarget {
	key: string
	label: string
	type: "Field" | "Earning" | "Deduction"
	required: boolean
}
export interface ColumnMapping {
	headers: string[]
	targets: MappingTarget[]
	mapping: Record<string, string | null>
	/** The columns CentHR recognises by itself. */
	auto: Record<string, string | null>
}

export const getReconciliation = (scope: Scope) => api<Reconciliation>(`${METHOD}.get_master_sheet_reconciliation`, args(scope))

/** Keeps the file as the cycle's master sheet, in place of the one it had, and compares it. */
export async function uploadMasterSheet(scope: Scope, file: File): Promise<Reconciliation> {
	const form = new FormData()
	form.append("file", file, file.name)
	form.append("from_date", scope.from)
	form.append("to_date", scope.to)
	if (scope.company) form.append("company", scope.company)
	const response = await fetch(`/api/method/${METHOD}.upload_master_sheet`, {
		method: "POST",
		body: form,
		headers: { "X-Frappe-CSRF-Token": window.csrf_token || "", Accept: "application/json" },
	})
	const body = await response.json().catch(() => ({}))
	if (!response.ok) throw new Error(serverMessage(body) || "Could not read the sheet")
	return body.message
}
export const removeMasterSheet = (scope: Scope) => api(`${METHOD}.remove_master_sheet`, args(scope))
export const downloadMasterTemplate = (scope: Scope) => downloadFile(`${METHOD}.download_master_sheet_template`, args(scope))
/** The reconciled rows as an Excel file: all of them, or those of one status. */
export const exportReconciliation = (scope: Scope, status?: ReconcileStatus) =>
	downloadFile(`${METHOD}.export_master_sheet_reconciliation`, { ...args(scope), status })

export const getColumnMapping = (scope: Scope) => api<ColumnMapping>(`${METHOD}.get_master_sheet_columns`, args(scope))
/** Saves the company's mapping; answers with the cycle's sheet compared again. */
export const saveColumnMapping = (scope: Scope, mapping: Record<string, string>) =>
	api<Reconciliation>(`${METHOD}.save_master_sheet_columns`, { ...args(scope), mapping })
