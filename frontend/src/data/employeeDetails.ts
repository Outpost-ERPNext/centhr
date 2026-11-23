import type { Ref } from "vue"
import { getList } from "@/data/list"

const MANAGER = "reports_to."

/**
 * For a form about one employee. The company is chosen first, the Employee field then lists that
 * company's active employees, and the chosen employee's details fill in at once. The server sets
 * the same details on save.
 *
 * `fields` names, for each field of the form, the Employee field it shows. "reports_to.designation"
 * is a field of the employee's line manager.
 */
export function useEmployeeDetails(doc: Ref<Record<string, any>>, fields: Record<string, string>) {
	const own = [...new Set(Object.values(fields).filter((f) => !f.startsWith(MANAGER)))]
	const ofManager = [...new Set(Object.values(fields).filter((f) => f.startsWith(MANAGER)).map((f) => f.slice(MANAGER.length)))]

	const linkFilters = {
		employee: (form: Record<string, any>) => ({ status: "Active", ...(form.company ? { company: form.company } : {}) }),
	}

	let request = 0
	async function fill(employee: string | null) {
		const id = ++request
		const details = employee ? await getEmployee(employee, ["company", "reports_to", ...own]) : null
		const manager = details?.reports_to && ofManager.length ? await getEmployee(details.reports_to, ofManager) : null
		// A slower answer for an employee chosen earlier must not overwrite the current one
		if (id !== request) return
		for (const [fieldname, source] of Object.entries(fields)) {
			const value = source.startsWith(MANAGER) ? manager?.[source.slice(MANAGER.length)] : details?.[source]
			doc.value[fieldname] = value ?? null
		}
		// Without an employee the company stays, so another employee of it can be chosen
		if (details) doc.value.company = details.company
	}

	function onChange(fieldname: string, value: any) {
		if (fieldname === "employee") fill(value)
	}

	return { linkFilters, onChange }
}

async function getEmployee(employee: string, fields: string[]) {
	const rows = await getList<Record<string, any>>({
		doctype: "Employee",
		fields: [...new Set(fields)],
		filters: [["name", "=", employee]],
		limit: 1,
		silent: true,
	}).catch(() => [])
	return rows[0] || null
}

export async function getEmployeeName(employee: string): Promise<string> {
	return (await getEmployee(employee, ["employee_name"]))?.employee_name || ""
}
