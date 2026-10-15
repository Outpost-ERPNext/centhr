import { sysdefaults } from "@/boot"

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

/** Parses a Frappe date (YYYY-MM-DD) as a local date, so the day never shifts by time zone. */
export function parseDate(value: string | null | undefined): Date | null {
	if (!value) return null
	const [y, m, d] = String(value).slice(0, 10).split("-").map(Number)
	if (!y || !m || !d) return null
	return new Date(y, m - 1, d)
}

export function toISODate(date: Date): string {
	const pad = (n: number) => String(n).padStart(2, "0")
	return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export const today = () => toISODate(new Date())

/** The current wall time in the site's time zone, as a Frappe datetime (YYYY-MM-DD HH:mm:ss). */
export function nowDatetime(): string {
	const now = new Date()
	const timeZone = sysdefaults().time_zone
	if (timeZone) {
		try {
			const parts = new Intl.DateTimeFormat("en-CA", {
				timeZone,
				hourCycle: "h23",
				year: "numeric",
				month: "2-digit",
				day: "2-digit",
				hour: "2-digit",
				minute: "2-digit",
				second: "2-digit",
			}).formatToParts(now)
			const get = (type: string) => parts.find((p) => p.type === type)?.value
			return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")}`
		} catch {
			// Unknown zone: fall back to browser time below
		}
	}
	return `${toISODate(now)} ${now.toTimeString().slice(0, 8)}`
}

export function addDays(value: string, days: number): string {
	const date = parseDate(value)!
	date.setDate(date.getDate() + days)
	return toISODate(date)
}

/** Formats a date with the site's System Settings date format. */
export function formatDate(value: string | null | undefined): string {
	const date = parseDate(value)
	if (!date) return ""
	const pad = (n: number) => String(n).padStart(2, "0")
	return sysdefaults()
		.date_format.replace("dd", pad(date.getDate()))
		.replace("mm", pad(date.getMonth() + 1))
		.replace("yyyy", String(date.getFullYear()))
}

/** Short human date as used in the design, for example "14 Oct 2026". */
export function formatDateShort(value: string | null | undefined): string {
	const date = parseDate(value)
	if (!date) return ""
	return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}`
}

export function formatDateTime(value: string | null | undefined): string {
	if (!value) return ""
	const [datePart, timePart = ""] = String(value).split(" ")
	return `${formatDate(datePart)} ${timePart.slice(0, 5)}`.trim()
}

/** "18:00:00" → "6:00 PM". */
export function formatTime(value: string | null | undefined): string {
	if (!value) return ""
	const [h, m = "0"] = String(value).split(":")
	const hour = Number(h)
	if (Number.isNaN(hour)) return ""
	return `${hour % 12 || 12}:${m.padStart(2, "0").slice(0, 2)} ${hour < 12 ? "AM" : "PM"}`
}

/** Start and end of a shift; an end before the start falls on the next day. */
export function shiftTiming(start: string | null | undefined, end: string | null | undefined): string {
	if (!start || !end) return ""
	const overnight = String(end).padStart(8, "0") < String(start).padStart(8, "0")
	return `${formatTime(start)} – ${formatTime(end)}${overnight ? " (next day)" : ""}`
}

export function weekday(value: string): string {
	const date = parseDate(value)
	return date ? WEEKDAYS[date.getDay()] : ""
}

export function isWeekend(value: string): boolean {
	const day = parseDate(value)?.getDay()
	return day === 0 || day === 6
}

export function formatNumber(value: number | string | null | undefined, precision?: number): string {
	if (value === null || value === undefined || value === "") return ""
	const num = Number(value)
	if (Number.isNaN(num)) return String(value)
	return num.toLocaleString(undefined, {
		minimumFractionDigits: precision ?? 0,
		maximumFractionDigits: precision ?? 2,
	})
}

export function formatCurrency(value: number | string | null | undefined, currency?: string | null): string {
	if (value === null || value === undefined || value === "") return ""
	const code = currency || sysdefaults().currency
	try {
		return Number(value).toLocaleString(undefined, code ? { style: "currency", currency: code } : {})
	} catch {
		return formatNumber(value, 2)
	}
}

export function initials(name: string | null | undefined): string {
	return (name || "?")
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2)
		.map((part) => part[0]!.toUpperCase())
		.join("")
}

/** Milliseconds the given time zone is ahead of UTC at the given instant. */
function zoneOffset(timeZone: string, timestamp: number): number {
	const parts = new Intl.DateTimeFormat("en-US", {
		timeZone,
		hourCycle: "h23",
		year: "numeric",
		month: "2-digit",
		day: "2-digit",
		hour: "2-digit",
		minute: "2-digit",
		second: "2-digit",
	}).formatToParts(new Date(timestamp))
	const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
	return Date.UTC(get("year"), get("month") - 1, get("day"), get("hour"), get("minute"), get("second")) - timestamp
}

/** Parses a Frappe datetime, which is wall time in the site's time zone, into an instant. */
export function parseDatetime(value: string): Date {
	const [datePart, timePart = "00:00:00"] = String(value).split(/[ T]/)
	const [y, m, d] = datePart!.split("-").map(Number)
	const [h = 0, mi = 0, sec = 0] = timePart.split(":").map(Number)
	const wall = Date.UTC(y!, m! - 1, d!, h, mi, Math.floor(sec))
	const timeZone = sysdefaults().time_zone
	if (!timeZone) return new Date(String(value).replace(" ", "T"))
	try {
		return new Date(wall - zoneOffset(timeZone, wall - zoneOffset(timeZone, wall)))
	} catch {
		return new Date(String(value).replace(" ", "T"))
	}
}

export function timeAgo(value: string | null | undefined): string {
	if (!value) return ""
	const date = parseDatetime(String(value))
	const seconds = Math.round((Date.now() - date.getTime()) / 1000)
	if (seconds < 60) return "just now"
	const minutes = Math.round(seconds / 60)
	if (minutes < 60) return `${minutes} min ago`
	const hours = Math.round(minutes / 60)
	if (hours < 24) return `${hours} h ago`
	const days = Math.round(hours / 24)
	if (days < 30) return `${days} d ago`
	return formatDateShort(String(value).slice(0, 10))
}

/** Plain value for display in detail grids and tables. */
export function displayValue(value: any, fieldtype?: string, currency?: string | null): string {
	if (value === null || value === undefined || value === "") return ""
	switch (fieldtype) {
		case "Date":
			return formatDate(value)
		case "Datetime":
			return formatDateTime(value)
		case "Check":
			return value ? "Yes" : "No"
		case "Currency":
			return formatCurrency(value, currency)
		case "Float":
		case "Percent":
			return formatNumber(value)
		case "Int":
			return formatNumber(value, 0)
		default:
			return String(value)
	}
}

/** The site's date format as a dayjs pattern, for frappe-ui date pickers. */
export function pickerDateFormat(): string {
	return sysdefaults().date_format.replace("dd", "DD").replace("mm", "MM").replace("yyyy", "YYYY")
}
