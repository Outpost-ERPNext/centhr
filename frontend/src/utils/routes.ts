/** CentHR page for a document, when the app has one. */
const ROUTES: Record<string, string> = {
	Employee: "/employees",
	"Leave Application": "/leave-applications",
	"Leave Allocation": "/leave-allocations",
	"Leave Type": "/leave-types",
	Attendance: "/attendance",
	"Employee Checkin": "/checkins",
	"Shift Type": "/shifts",
}

export function routeFor(doctype: string | undefined, name: string | null | undefined): string | null {
	if (!doctype || !name || !ROUTES[doctype]) return null
	return `${ROUTES[doctype]}/${encodeURIComponent(name)}`
}

export function listRouteFor(doctype: string): string | null {
	return ROUTES[doctype] || null
}
