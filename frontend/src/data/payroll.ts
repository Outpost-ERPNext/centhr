import { api } from "@/data/api"
import { parseDate, toISODate } from "@/utils/format"

export interface PayrollCycle {
	from_date: string
	to_date: string
	/** The Payroll Period the dates come from, or null for the calendar-month fallback. */
	payroll_period: string | null
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const cache = new Map<string, Promise<PayrollCycle>>()

function calendarMonth(date: string): PayrollCycle {
	const d = parseDate(date)!
	return {
		from_date: toISODate(new Date(d.getFullYear(), d.getMonth(), 1)),
		to_date: toISODate(new Date(d.getFullYear(), d.getMonth() + 1, 0)),
		payroll_period: null,
	}
}

/** The company's payroll period dates that contain `date`, or the calendar month when it has none. */
export function getPayrollCycle(company: string | null | undefined, date: string): Promise<PayrollCycle> {
	if (!company) return Promise.resolve(calendarMonth(date))
	const key = `${company}|${date}`
	if (!cache.has(key)) {
		const request = api<PayrollCycle | null>("centhr.api.attendance.get_payroll_cycle", { company, date }, { silent: true })
			.then((cycle) => (cycle ? { ...cycle, payroll_period: cycle.payroll_period || null } : calendarMonth(date)))
			// No Payroll Period permission falls back to the calendar month too
			.catch(() => calendarMonth(date))
		cache.set(key, request)
	}
	return cache.get(key)!
}

/** "October 2026" for a whole month, else "26 Sep – 25 Oct 2026". */
export function cycleLabel(from: string, to: string): string {
	const a = parseDate(from)
	const b = parseDate(to)
	if (!a || !b) return ""
	const monthEnd = new Date(b.getFullYear(), b.getMonth() + 1, 0).getDate()
	if (a.getDate() === 1 && b.getDate() === monthEnd && a.getMonth() === b.getMonth() && a.getFullYear() === b.getFullYear()) {
		return `${new Intl.DateTimeFormat("en", { month: "long" }).format(a)} ${a.getFullYear()}`
	}
	const start = `${a.getDate()} ${MONTHS[a.getMonth()]}${a.getFullYear() !== b.getFullYear() ? ` ${a.getFullYear()}` : ""}`
	return `${start} – ${b.getDate()} ${MONTHS[b.getMonth()]} ${b.getFullYear()}`
}

export interface PayrollYear {
	/** Year shown in the picker: the calendar year the payroll year starts in. */
	label: string
	from_date: string
	to_date: string
	payroll_period: string | null
	periods: { from_date: string; to_date: string }[]
}

const yearCache = new Map<string, Promise<PayrollYear[]>>()

function calendarYears(): PayrollYear[] {
	const current = new Date().getFullYear()
	return Array.from({ length: 6 }, (_, i) => current + 1 - i).map((year) => ({
		label: String(year),
		from_date: `${year}-01-01`,
		to_date: `${year}-12-31`,
		payroll_period: null,
		periods: Array.from({ length: 12 }, (_, m) => {
			const month = calendarMonth(toISODate(new Date(year, m, 1)))
			return { from_date: month.from_date, to_date: month.to_date }
		}),
	}))
}

/** The company's payroll years (Payroll Periods) with their months, newest first; calendar years when it has none. */
export function getPayrollYears(company: string | null | undefined): Promise<PayrollYear[]> {
	if (!company) return Promise.resolve(calendarYears())
	if (!yearCache.has(company)) {
		const request = api<Omit<PayrollYear, "label">[]>("centhr.api.attendance.get_payroll_years", { company }, { silent: true })
			.then((years) =>
				years.length ? years.map((y) => ({ ...y, label: y.from_date.slice(0, 4) })) : calendarYears()
			)
			.catch(() => calendarYears())
		yearCache.set(company, request)
	}
	return yearCache.get(company)!
}
