import { getList, type Filter } from "./list"
import { can, getReadableFields } from "./permissions"
import { today } from "@/utils/format"

export interface ShiftAssignmentSummary {
	employees: number
	companies: string[]
}

/** Submitted, active Shift Assignments that cover today, as list filters. */
function currentAssignmentFilters(): { filters: Filter[]; or_filters: Filter[] } {
	return {
		filters: [
			["docstatus", "=", 1],
			["status", "=", "Active"],
			["start_date", "<=", today()],
		],
		or_filters: [
			["end_date", "is", "not set"],
			["end_date", ">=", today()],
		],
	}
}

/**
 * Employees and companies currently assigned to each shift type. Shift Type has no
 * company of its own, so its entities come from its assignments. Empty when the user
 * cannot read Shift Assignment; the server applies their permissions to every row.
 */
export async function getShiftAssignmentSummary(shiftTypes: string[]): Promise<Record<string, ShiftAssignmentSummary>> {
	if (!shiftTypes.length || !can("Shift Assignment").read) return {}
	const readable = await getReadableFields("Shift Assignment")
	const allowed = (f: string) => !readable.length || readable.includes(f)
	if (!allowed("shift_type")) return {}
	const fields = ["shift_type", ...["employee", "company"].filter(allowed)]
	const { filters, or_filters } = currentAssignmentFilters()
	const rows = await getList<{ shift_type: string; employee?: string; company?: string }>({
		doctype: "Shift Assignment",
		fields,
		filters: [["shift_type", "in", shiftTypes], ...filters],
		or_filters,
		limit: 0,
		silent: true,
	}).catch(() => [])

	const seen: Record<string, { employees: Set<string>; companies: Set<string> }> = {}
	for (const row of rows) {
		const entry = (seen[row.shift_type] ||= { employees: new Set(), companies: new Set() })
		if (row.employee) entry.employees.add(row.employee)
		if (row.company) entry.companies.add(row.company)
	}
	return Object.fromEntries(
		Object.entries(seen).map(([shift, v]) => [shift, { employees: v.employees.size, companies: [...v.companies].sort() }])
	)
}

/** Shift types with a current assignment in the company, for the list's company filter. */
export async function getShiftTypesForCompany(company: string): Promise<string[]> {
	const { filters, or_filters } = currentAssignmentFilters()
	const rows = await getList<{ shift_type: string }>({
		doctype: "Shift Assignment",
		fields: ["shift_type"],
		filters: [["company", "=", company], ...filters],
		or_filters,
		group_by: "shift_type",
		limit: 0,
	})
	return rows.map((r) => r.shift_type)
}
