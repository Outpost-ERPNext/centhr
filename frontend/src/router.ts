import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import { isLoggedIn, loadUser } from "@/data/session"
import { loadPermissions } from "@/data/permissions"

export const APP_DOCTYPES = ["Employee", "Leave Application", "Leave Allocation", "Leave Type", "Attendance", "Attendance Request", "Employee Checkin", "Shift Type", "Shift Assignment", "Shift Assignment Tool", "Holiday List", "Department", "Employee Grade", "Designation", "Salary Structure Assignment", "Payroll Entry", "Salary Slip"]

/** List, new and detail routes for one DocType page set. */
function docRoutes(path: string, name: string, list: () => Promise<any>, detail: () => Promise<any>) {
	return [
		{ path, name: `${name}List`, component: list },
		{ path: `${path}/new`, name: `${name}New`, component: detail, props: { name: null } },
		{ path: `${path}/:name`, name: `${name}Detail`, component: detail, props: true },
	]
}

const routes: RouteRecordRaw[] = [
	{
		path: "/login",
		name: "Login",
		component: () => import("@/pages/Login.vue"),
		meta: { public: true },
	},
	{
		path: "/",
		component: () => import("@/components/layout/AppLayout.vue"),
		children: [
			{ path: "", name: "Dashboard", component: () => import("@/pages/Dashboard.vue") },
			...docRoutes(
				"employees",
				"Employee",
				() => import("@/pages/employees/EmployeeList.vue"),
				() => import("@/pages/employees/EmployeeDetail.vue")
			),
			...docRoutes(
				"leave-applications",
				"LeaveApplication",
				() => import("@/pages/leave-applications/LeaveApplicationList.vue"),
				() => import("@/pages/leave-applications/LeaveApplicationDetail.vue")
			),
			...docRoutes(
				"leave-allocations",
				"LeaveAllocation",
				() => import("@/pages/leave-allocations/LeaveAllocationList.vue"),
				() => import("@/pages/leave-allocations/LeaveAllocationDetail.vue")
			),
			...docRoutes(
				"leave-types",
				"LeaveType",
				() => import("@/pages/leave-types/LeaveTypeList.vue"),
				() => import("@/pages/leave-types/LeaveTypeDetail.vue")
			),
			...docRoutes(
				"attendance",
				"Attendance",
				() => import("@/pages/attendance/AttendanceList.vue"),
				() => import("@/pages/attendance/AttendanceDetail.vue")
			),
			...docRoutes(
				"attendance-requests",
				"AttendanceRequest",
				() => import("@/pages/attendance-requests/AttendanceRequestList.vue"),
				() => import("@/pages/attendance-requests/AttendanceRequestDetail.vue")
			),
			...docRoutes(
				"checkins",
				"EmployeeCheckin",
				() => import("@/pages/checkins/EmployeeCheckinList.vue"),
				() => import("@/pages/checkins/EmployeeCheckinDetail.vue")
			),
			...docRoutes(
				"shifts",
				"ShiftType",
				() => import("@/pages/shifts/ShiftTypeList.vue"),
				() => import("@/pages/shifts/ShiftTypeDetail.vue")
			),
			...docRoutes(
				"shift-assignments",
				"ShiftAssignment",
				() => import("@/pages/shift-assignments/ShiftAssignmentList.vue"),
				() => import("@/pages/shift-assignments/ShiftAssignmentDetail.vue")
			),
			...docRoutes(
				"holiday-lists",
				"HolidayList",
				() => import("@/pages/holiday-lists/HolidayListList.vue"),
				() => import("@/pages/holiday-lists/HolidayListDetail.vue")
			),
			...docRoutes(
				"departments",
				"Department",
				() => import("@/pages/departments/DepartmentList.vue"),
				() => import("@/pages/departments/DepartmentDetail.vue")
			),
			...docRoutes(
				"grades",
				"EmployeeGrade",
				() => import("@/pages/grades/EmployeeGradeList.vue"),
				() => import("@/pages/grades/EmployeeGradeDetail.vue")
			),
			...docRoutes(
				"designations",
				"Designation",
				() => import("@/pages/designations/DesignationList.vue"),
				() => import("@/pages/designations/DesignationDetail.vue")
			),
			...docRoutes(
				"salary-structure-assignments",
				"SalaryStructureAssignment",
				() => import("@/pages/salary-structure-assignments/SalaryStructureAssignmentList.vue"),
				() => import("@/pages/salary-structure-assignments/SalaryStructureAssignmentDetail.vue")
			),
			{
				path: "shift-assignment-tool",
				name: "ShiftAssignmentTool",
				component: () => import("@/pages/shift-assignment-tool/ShiftAssignmentTool.vue"),
			},
			{ path: "payroll-processing", redirect: { name: "PayrollEntryList" } },
			...docRoutes(
				"payroll-processing/payroll-entries",
				"PayrollEntry",
				() => import("@/pages/payroll-processing/PayrollEntryList.vue"),
				() => import("@/pages/payroll-processing/PayrollEntryDetail.vue")
			),
			...docRoutes(
				"payroll-processing/salary-slips",
				"SalarySlip",
				() => import("@/pages/payroll-processing/SalarySlipList.vue"),
				() => import("@/pages/payroll-processing/SalarySlipDetail.vue")
			),
		] as RouteRecordRaw[],
	},
	{ path: "/:pathMatch(.*)*", redirect: "/" },
]

const router = createRouter({
	history: createWebHistory("/centhr"),
	routes,
})

router.beforeEach(async (to) => {
	if (to.meta.public) {
		if (to.name === "Login" && isLoggedIn()) {
			return safeRedirect(to.query.redirect)
		}
		return true
	}
	if (!isLoggedIn()) {
		return { name: "Login", query: to.fullPath !== "/" ? { redirect: to.fullPath } : {} }
	}
	await loadUser()
	if (!isLoggedIn()) {
		return { name: "Login", query: { expired: "1", redirect: to.fullPath } }
	}
	await loadPermissions(APP_DOCTYPES).catch(() => undefined)
	return true
})

/** Only follow redirects to paths inside CentHR. */
export function safeRedirect(value: unknown): string {
	const path = typeof value === "string" ? value : ""
	return path.startsWith("/") && !path.startsWith("//") && !path.startsWith("/login") ? path : "/"
}

export default router
