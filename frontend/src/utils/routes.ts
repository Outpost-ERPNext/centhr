/** CentHR page for a document, when the app has one. */
const ROUTES: Record<string, string> = {
	Employee: "/employees",
	"Leave Application": "/leave-applications",
	"Leave Allocation": "/leave-allocations",
	"Leave Type": "/leave-types",
	Attendance: "/attendance",
	"Attendance Request": "/attendance-requests",
	"Employee Checkin": "/checkins",
	"Shift Type": "/shifts",
	"Shift Assignment": "/shift-assignments",
	"Holiday List": "/holiday-lists",
	Department: "/departments",
	"Employee Grade": "/grades",
	Designation: "/designations",
	"Salary Structure Assignment": "/salary-structure-assignments",
	"Payroll Entry": "/payroll-processing/payroll-entries",
	"Salary Slip": "/payroll-processing/salary-slips",
}

export function routeFor(doctype: string | undefined, name: string | null | undefined): string | null {
	if (!doctype || !name || !ROUTES[doctype]) return null
	return `${ROUTES[doctype]}/${encodeURIComponent(name)}`
}

export function listRouteFor(doctype: string): string | null {
	return ROUTES[doctype] || null
}
