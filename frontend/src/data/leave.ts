import { getList } from "@/data/list"
import { addDays } from "@/utils/format"

export interface PendingLeave {
	name: string
	leave_type: string
	half_day: boolean
}

/**
 * Days covered by leave that is applied for but not yet approved (open, unsubmitted Leave Applications),
 * keyed `employee|date`. Attendance has no status for this, so the views show it as "PLA" without storing it.
 * Returns nothing when the user cannot read Leave Applications.
 */
export async function getPendingLeaves(
	employees: string[],
	from: string,
	to: string
): Promise<Record<string, PendingLeave>> {
	if (!employees.length || !from || !to) return {}
	const rows = await getList<{
		name: string
		employee: string
		from_date: string
		to_date: string
		leave_type: string
		half_day: number
		half_day_date: string | null
	}>({
		doctype: "Leave Application",
		fields: ["name", "employee", "from_date", "to_date", "leave_type", "half_day", "half_day_date"],
		filters: [
			["employee", "in", employees],
			["docstatus", "=", 0],
			["status", "=", "Open"],
			["from_date", "<=", to],
			["to_date", ">=", from],
		],
		limit: 0,
		silent: true,
	}).catch(() => [])

	const out: Record<string, PendingLeave> = {}
	for (const row of rows) {
		const start = row.from_date > from ? row.from_date : from
		const end = row.to_date < to ? row.to_date : to
		for (let d = start; d <= end; d = addDays(d, 1)) {
			const halfDay = !!row.half_day && (!row.half_day_date || row.half_day_date === d)
			out[`${row.employee}|${d}`] = { name: row.name, leave_type: row.leave_type, half_day: halfDay }
		}
	}
	return out
}
