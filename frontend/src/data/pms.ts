import { api } from "@/data/api"
import { getList } from "@/data/list"
import { toISODate } from "@/utils/format"
import type { Tone } from "@/utils/status"

const METHOD = "centhr.pms.api"

export const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

/** The month every KPI page works on; company and department narrow it. */
export interface KpiScope {
	fiscalYear: string
	month: string
	company: string
	department: string
}

export interface KpiResultSummary {
	name: string
	docstatus: number
	overall_score: number
	remark: string | null
}

/** One employee's KPI Template of the month, with the KPI Result made from it. */
export interface KpiRow {
	name: string
	employee: string
	employee_name: string
	company: string
	department: string | null
	designation: string | null
	reviewer: string | null
	docstatus: number
	result: KpiResultSummary | null
}

export type KpiStage = "template" | "fill" | "done"

/** Where an employee's month stands: template not submitted yet, result to fill in, or result submitted. */
export function kpiStage(row: KpiRow): KpiStage {
	if (!row.result) return "template"
	return row.result.docstatus === 1 ? "done" : "fill"
}

export const KPI_STAGES: Record<KpiStage, { label: string; tone: Tone }> = {
	template: { label: "Template in draft", tone: "gray" },
	fill: { label: "Result to fill in", tone: "amber" },
	done: { label: "Result submitted", tone: "green" },
}

export function getKpiDashboard(scope: KpiScope) {
	return api<KpiRow[]>(`${METHOD}.get_kpi_dashboard`, {
		fiscal_year: scope.fiscalYear,
		month: scope.month,
		company: scope.company || undefined,
		department: scope.department || undefined,
	})
}

export function createKpiTemplates(args: {
	fiscal_year: string
	month: string
	department: string
	designation?: string | null
	items: Record<string, any>[]
}) {
	return api<{ created: string[]; skipped: number }>(`${METHOD}.create_kpi_templates`, {
		...args,
		designation: args.designation || undefined,
	})
}

export function copyKpiTemplates(company: string) {
	return api<{ created: string[]; month: string; source: string }>(`${METHOD}.copy_kpi_templates`, { company })
}

/** The fiscal year today falls in, to open the KPI pages on the current month. */
export async function getCurrentFiscalYear(): Promise<string> {
	const today = toISODate(new Date())
	const rows = await getList<{ name: string }>({
		doctype: "Fiscal Year",
		fields: ["name"],
		filters: [
			["year_start_date", "<=", today],
			["year_end_date", ">=", today],
			["disabled", "=", 0],
		],
		order_by: "year_start_date desc",
		limit: 1,
		silent: true,
	}).catch(() => [])
	return rows[0]?.name || ""
}

export function currentMonth(): string {
	return MONTHS[new Date().getMonth()]
}

export interface PeerMappingStats {
	employees: number
	created: number
	locked: number
	peers_added: number
	peers_removed: number
}

export function runPeerMapping(company: string) {
	return api<PeerMappingStats>(`${METHOD}.run_peer_mapping`, { company })
}

export function setPeerMappingLock(employee: string, locked: boolean) {
	return api<boolean>(`${METHOD}.set_peer_mapping_lock`, { employee, locked: locked ? 1 : 0 })
}
