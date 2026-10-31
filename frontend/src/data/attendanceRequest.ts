import { getList } from "@/data/list"
import { addDays } from "@/utils/format"

export interface PendingRequest {
	name: string
	reason: string
	half_day: boolean
	include_holidays: boolean
}

/**
 * Days covered by Attendance Requests that are not submitted yet (drafts), keyed `employee|date`.
 * HRMS marks the attendance only on submission, so the views show these as "ARR" without storing anything.
 * Returns nothing when the user cannot read Attendance Requests.
 */
export async function getPendingRequests(
	employees: string[],
	from: string,
	to: string
): Promise<Record<string, PendingRequest>> {
	if (!employees.length || !from || !to) return {}
	const rows = await getList<{
		name: string
		employee: string
		from_date: string
		to_date: string
		reason: string
		half_day: number
		half_day_date: string | null
		include_holidays: number
	}>({
		doctype: "Attendance Request",
		fields: ["name", "employee", "from_date", "to_date", "reason", "half_day", "half_day_date", "include_holidays"],
		filters: [
			["employee", "in", employees],
			["docstatus", "=", 0],
			["from_date", "<=", to],
			["to_date", ">=", from],
		],
		limit: 0,
		silent: true,
	}).catch(() => [])

	const out: Record<string, PendingRequest> = {}
	for (const row of rows) {
		const start = row.from_date > from ? row.from_date : from
		const end = row.to_date < to ? row.to_date : to
		for (let d = start; d <= end; d = addDays(d, 1)) {
			out[`${row.employee}|${d}`] = {
				name: row.name,
				reason: row.reason,
				half_day: !!row.half_day && row.half_day_date === d,
				include_holidays: !!row.include_holidays,
			}
		}
	}
	return out
}

/**
 * Employees with pending leave (open, unapproved Leave Applications) or pending attendance requests
 * (draft Attendance Requests), optionally only those overlapping `from`–`to` and in one company.
 * Used by the PLA / ARR filters of the attendance views.
 */
export async function getEmployeesWithPending(
	kind: "leave" | "request",
	{ from, to, company }: { from?: string; to?: string; company?: string | null } = {}
): Promise<string[]> {
	const filters: [string, string, any][] = [["docstatus", "=", 0]]
	if (to) filters.push(["from_date", "<=", to])
	if (from) filters.push(["to_date", ">=", from])
	if (company) filters.push(["company", "=", company])
	if (kind === "leave") filters.push(["status", "=", "Open"])
	const rows = await getList<{ employee: string }>({
		doctype: kind === "leave" ? "Leave Application" : "Attendance Request",
		fields: ["employee"],
		filters,
		group_by: "employee",
		limit: 0,
		silent: true,
	}).catch(() => [])
	return rows.map((r) => r.employee)
}
