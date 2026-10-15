<template>
	<div class="flex min-h-0 flex-1 flex-col">
		<div class="flex flex-wrap items-center gap-2 px-5 py-3">
			<div class="w-[calc(50%-4px)] sm:w-44">
				<LinkField v-model="company" doctype="Company" placeholder="Company" />
			</div>
			<div class="w-[calc(50%-4px)] sm:w-44">
				<LinkField v-model="department" doctype="Department" placeholder="Department" />
			</div>
			<PayrollCycleNav v-model:from="fromDate" v-model:to="toDate" :company="company" />
			<span class="text-[13px] text-ch-ink-3">Not marked: <span class="tabular-nums text-ch-ink">{{ unmarked }}</span></span>
			<span v-if="pendingCount" class="text-[13px] text-ch-ink-3">
				Pending leave: <span class="tabular-nums text-ch-ink">{{ pendingCount }}</span>
			</span>
			<Button
				v-if="canMark && picked.length"
				class="ml-auto"
				variant="solid"
				:label="`Mark for ${picked.length} employee${picked.length === 1 ? '' : 's'}`"
				@click="$emit('mark', picked, { from: fromDate, to: toDate, company })"
			/>
		</div>

		<div class="min-h-0 flex-1 overflow-auto px-5 pb-4">
			<div v-if="loading && !employees.length" class="py-16 text-center text-sm text-ch-ink-3">Loading…</div>
			<div v-else-if="!employees.length" class="py-16 text-center text-sm text-ch-ink-3">No active employees.</div>
			<table v-else class="border-separate border-spacing-0 text-[12.5px]">
				<thead>
					<tr>
						<th class="sticky left-0 top-0 z-[3] min-w-[220px] border-b border-ch-line bg-ch-bg px-2 py-2 text-left font-normal text-ch-ink-3">
							<label class="flex items-center gap-2">
								<Checkbox
									v-if="canMark"
									:model-value="picked.length === employees.length"
									aria-label="Select all employees"
									@update:model-value="picked = picked.length === employees.length ? [] : employees.map((e) => e.name)"
								/>
								Employee
							</label>
						</th>
						<th
							v-for="d in dates"
							:key="d"
							class="sticky top-0 z-[2] min-w-[34px] border-b border-ch-line px-0.5 py-1 text-center font-normal"
							:class="offForAll(d) ? 'bg-ch-weekend text-ch-ink-4' : 'bg-ch-bg text-ch-ink-3'"
						>
							<div class="text-[11px]">{{ weekday(d).slice(0, 2) }}</div>
							<div class="tabular-nums" :class="d === todayDate ? 'font-semibold text-ch-blue-ink' : ''">{{ Number(d.slice(8)) }}</div>
						</th>
						<th class="sticky top-0 z-[2] border-b border-ch-line bg-ch-bg px-2 text-center font-normal text-ch-ink-3">P</th>
						<th class="sticky top-0 z-[2] border-b border-ch-line bg-ch-bg px-2 text-center font-normal text-ch-ink-3">A</th>
						<th class="sticky top-0 z-[2] border-b border-ch-line bg-ch-bg px-2 text-center font-normal text-ch-ink-3">L</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="emp in employees" :key="emp.name">
						<td class="sticky left-0 z-[1] border-b border-ch-line bg-ch-bg px-2 py-1.5">
							<label class="flex items-center gap-2">
								<Checkbox
									v-if="canMark"
									:model-value="picked.includes(emp.name)"
									:aria-label="`Select ${emp.employee_name}`"
									@update:model-value="toggle(emp.name)"
								/>
								<RouterLink :to="`/employees/${encodeURIComponent(emp.name)}`" class="min-w-0">
									<div class="truncate font-medium text-ch-ink">{{ emp.employee_name }}</div>
									<div class="truncate text-[11.5px] text-ch-ink-3">{{ emp.name }}</div>
								</RouterLink>
							</label>
						</td>
						<td
							v-for="d in dates"
							:key="d"
							class="border-b border-ch-line px-0.5 py-1 text-center"
							:class="isHoliday(emp.name, d) ? 'bg-ch-weekend' : ''"
							:title="isHoliday(emp.name, d) ? (holidays[emp.name]?.[d] ? 'Weekly off' : 'Holiday') : undefined"
						>
							<RouterLink
								v-if="cell(emp.name, d)"
								:to="`/attendance/${encodeURIComponent(cell(emp.name, d)!.name)}`"
								class="inline-flex h-5 min-w-7 items-center justify-center rounded-[5px] px-1 text-[10.5px] font-semibold"
								:class="cell(emp.name, d)!.docstatus === 0 ? 'outline outline-1 outline-dashed' : ''"
								:style="asPending(emp.name, d) ? pendingStyle : chipStyle(cell(emp.name, d)!.status)"
								:title="recordTitle(emp.name, d)"
							>
								{{ asPending(emp.name, d) ? PENDING_LEAVE.code : ATTENDANCE_CODES[cell(emp.name, d)!.status] || "?" }}
							</RouterLink>
							<RouterLink
								v-else-if="asPending(emp.name, d)"
								:to="`/leave-applications/${encodeURIComponent(asPending(emp.name, d)!.name)}`"
								class="inline-flex h-5 min-w-7 items-center justify-center rounded-[5px] px-1 text-[10.5px] font-semibold"
								:style="pendingStyle"
								:title="pendingTitle(asPending(emp.name, d)!)"
							>
								{{ PENDING_LEAVE.code }}
							</RouterLink>
							<span v-else-if="isHoliday(emp.name, d)" class="text-[10.5px] text-ch-ink-4">H</span>
							<span v-else-if="d <= todayDate && emp.date_of_joining <= d" class="text-ch-ink-4">·</span>
						</td>
						<td class="border-b border-ch-line px-2 text-center tabular-nums">{{ total(emp.name, ["Present", "Work From Home"]) }}</td>
						<td class="border-b border-ch-line px-2 text-center tabular-nums">{{ total(emp.name, ["Absent"]) }}</td>
						<td class="border-b border-ch-line px-2 text-center tabular-nums">{{ total(emp.name, ["On Leave", "Half Day"]) }}</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div class="flex flex-wrap items-center gap-3 border-t border-ch-line px-5 py-2 text-[12px] text-ch-ink-3">
			<span v-for="status in ATTENDANCE_SUMMARY_STATUSES" :key="status" class="flex items-center gap-1.5">
				<span
					class="inline-flex h-4 min-w-6 items-center justify-center rounded-[4px] px-1 text-[10px] font-semibold"
					:style="chipStyle(status)"
				>{{ ATTENDANCE_CODES[status] }}</span>
				{{ status }}
			</span>
			<span class="flex items-center gap-1.5">
				<span
					class="inline-flex h-4 min-w-6 items-center justify-center rounded-[4px] px-1 text-[10px] font-semibold"
					:style="pendingStyle"
				>{{ PENDING_LEAVE.code }}</span>
				{{ PENDING_LEAVE.label }}
			</span>
			<span class="flex items-center gap-1.5"><span class="flex h-4 w-6 items-center justify-center rounded-[4px] bg-ch-weekend text-[10px]">H</span> Holiday or weekly off</span>
			<Pager v-model:page="page" v-model:page-size="pageSize" :total="employeeTotal" class="ml-auto !border-0 !p-0" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Checkbox } from "frappe-ui"
import LinkField from "@/components/fields/LinkField.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import Pager from "@/components/Pager.vue"
import { api } from "@/data/api"
import { getCount, getList, type Filter } from "@/data/list"
import { addDays, parseDate, today, weekday } from "@/utils/format"
import { readStorage, writeStorage } from "@/utils/storage"
import { getPendingLeaves, type PendingLeave } from "@/data/leave"
import { ATTENDANCE_CODES, ATTENDANCE_SUMMARY_STATUSES, PENDING_LEAVE, toneFor } from "@/utils/status"

defineProps<{ canMark: boolean }>()
defineEmits<{ mark: [employees: string[], range: { from: string; to: string; company: string | null }] }>()

const todayDate = today()

// Each company has its own payroll period, so the register shows one company at a time
const company = ref<string | null>(readStorage("centhr-register-company", "") || null)
const department = ref<string | null>(null)
const fromDate = ref("")
const toDate = ref("")
const page = ref(1)
const pageSize = ref(20)
const loading = ref(true)
const employees = ref<{ name: string; employee_name: string; date_of_joining: string }[]>([])
const employeeTotal = ref(0)
const records = ref<Record<string, { name: string; status: string; docstatus: number }>>({})
const picked = ref<string[]>([])
/** Holiday dates per employee, from their Holiday List Assignment (true = weekly off). */
const holidays = ref<Record<string, Record<string, boolean>>>({})
/** Leave applied for but not approved yet, per `employee|date`. */
const pendingLeaves = ref<Record<string, PendingLeave>>({})

const isHoliday = (employee: string, date: string) => date in (holidays.value[employee] || {})
const offForAll = (date: string) =>
	employees.value.length > 0 && employees.value.every((e) => isHoliday(e.name, date))

const dates = computed(() => {
	if (!fromDate.value || !toDate.value) return []
	const days = dayCount(toDate.value, fromDate.value) + 1
	return Array.from({ length: Math.max(days, 0) }, (_, i) => addDays(fromDate.value, i))
})

function dayCount(to: string, from: string) {
	return Math.round((parseDate(to)!.getTime() - parseDate(from)!.getTime()) / 86400000)
}

function toggle(name: string) {
	picked.value = picked.value.includes(name) ? picked.value.filter((n) => n !== name) : [...picked.value, name]
}

const cell = (employee: string, date: string) => records.value[`${employee}|${date}`]

/**
 * The pending leave to show as PLA on this day: on a day with no attendance (unless it is a holiday),
 * or in place of an Absent record, which HRMS turns into On Leave once the leave is approved.
 */
function asPending(employee: string, date: string): PendingLeave | null {
	const leave = pendingLeaves.value[`${employee}|${date}`]
	if (!leave) return null
	const record = cell(employee, date)
	if (record) return record.status === "Absent" ? leave : null
	return isHoliday(employee, date) ? null : leave
}

const pendingStyle = { background: `var(--ch-${PENDING_LEAVE.tone}-bg)`, color: `var(--ch-${PENDING_LEAVE.tone}-ink)` }

function pendingTitle(leave: PendingLeave) {
	return `${PENDING_LEAVE.label}: ${leave.name} (${leave.leave_type}${leave.half_day ? ", half day" : ""})`
}

function recordTitle(employee: string, date: string) {
	const record = cell(employee, date)!
	const draft = record.docstatus === 0 ? " (draft)" : ""
	const leave = asPending(employee, date)
	return leave ? `${record.status} recorded${draft} · ${pendingTitle(leave)}` : `${record.status}${draft}`
}

function total(employee: string, statuses: string[]) {
	return dates.value.filter((d) => statuses.includes(cell(employee, d)?.status || "") && !asPending(employee, d)).length
}

const unmarked = computed(() => {
	let count = 0
	for (const emp of employees.value) {
		for (const d of dates.value) {
			if (
				d <= todayDate &&
				emp.date_of_joining <= d &&
				!isHoliday(emp.name, d) &&
				!cell(emp.name, d) &&
				!pendingLeaves.value[`${emp.name}|${d}`]
			)
				count++
		}
	}
	return count
})

const pendingCount = computed(() => {
	let count = 0
	for (const emp of employees.value) for (const d of dates.value) if (asPending(emp.name, d)) count++
	return count
})

function chipStyle(status: string) {
	const tone = toneFor("Attendance", status)
	return { background: `var(--ch-${tone}-bg)`, color: `var(--ch-${tone}-ink)` }
}

let requestId = 0
async function load() {
	if (!dates.value.length) return
	const id = ++requestId
	loading.value = true
	try {
		const empFilters: Filter[] = [["status", "=", "Active"]]
		if (company.value) empFilters.push(["company", "=", company.value])
		if (department.value) empFilters.push(["department", "=", department.value])
		const [emps, count] = await Promise.all([
			getList<{ name: string; employee_name: string; date_of_joining: string }>({
				doctype: "Employee",
				fields: ["name", "employee_name", "date_of_joining"],
				filters: empFilters,
				order_by: "employee_name asc",
				start: (page.value - 1) * pageSize.value,
				limit: pageSize.value,
			}),
			getCount("Employee", empFilters),
		])
		// Only this page of employees and this month, so the register stays light
		const range = [dates.value[0], dates.value[dates.value.length - 1]]
		const holidayRequest = emps.length
			? api<Record<string, Record<string, boolean>>>(
					"centhr.api.attendance.get_holidays_for_employees",
					{ employees: emps.map((e) => e.name), from_date: range[0], to_date: range[1] },
					{ silent: true }
				).catch(() => ({}))
			: Promise.resolve({})
		const pendingRequest = getPendingLeaves(
			emps.map((e) => e.name),
			range[0],
			range[1]
		)
		const rows = emps.length
			? await getList<{ name: string; employee: string; attendance_date: string; status: string; docstatus: number }>({
					doctype: "Attendance",
					fields: ["name", "employee", "attendance_date", "status", "docstatus"],
					filters: [
						["employee", "in", emps.map((e) => e.name)],
						["attendance_date", "between", range],
						["docstatus", "<", 2],
					],
					limit: 0,
				})
			: []
		const [holidayMap, pendingMap] = await Promise.all([holidayRequest, pendingRequest])
		if (id !== requestId) return
		holidays.value = holidayMap
		pendingLeaves.value = pendingMap
		employees.value = emps
		employeeTotal.value = count
		records.value = Object.fromEntries(rows.map((r) => [`${r.employee}|${r.attendance_date}`, r]))
		picked.value = picked.value.filter((n) => emps.some((e) => e.name === n))
	} finally {
		if (id === requestId) loading.value = false
	}
}

watch([company, department, pageSize], () => {
	if (page.value !== 1) page.value = 1
	else load()
})
watch(company, (c) => writeStorage("centhr-register-company", c || ""))
// The payroll period nav sets both dates; load once per change
watch(() => `${fromDate.value}|${toDate.value}`, load)
watch(page, load)

// Start on a company so the register follows a payroll period: the last one used, or the first permitted
if (!company.value) {
	getList<{ name: string }>({ doctype: "Company", fields: ["name"], order_by: "name asc", limit: 1 })
		.then((rows) => {
			if (!company.value && rows[0]) company.value = rows[0].name
		})
		.catch(() => {})
}

defineExpose({ reload: load })
</script>
