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
	"Cost Center": "/cost-centers",
	Channel: "/channels",
	"Employment Type": "/employment-types",
	Gender: "/genders",
	"Salary Structure Assignment": "/salary-structure-assignments",
	"Salary Component": "/salary-components",
	"Salary Structure": "/salary-structures",
	"Payroll Entry": "/payroll-processing/payroll-entries",
	"Salary Slip": "/payroll-processing/salary-slips",
	"PMS Settings": "/pms/settings",
	"PMS Question": "/pms/questions",
	"PMS Question Trait": "/pms/question-traits",
	"KPI UOM": "/pms/kpi-uoms",
	"KPI Template": "/pms/kpi-templates",
	"KPI Result": "/pms/kpi-results",
	"PMS Employee Relationship": "/pms/relationships",
	"PMS 360 Degree": "/pms/360-setup",
	"PMS Questionnaire": "/pms/questionnaires",
	"PMS Score Sheet": "/pms/score-sheets",
}

export function routeFor(doctype: string | undefined, name: string | null | undefined): string | null {
	if (!doctype || !name || !ROUTES[doctype]) return null
	return `${ROUTES[doctype]}/${encodeURIComponent(name)}`
}

export function listRouteFor(doctype: string): string | null {
	return ROUTES[doctype] || null
}
