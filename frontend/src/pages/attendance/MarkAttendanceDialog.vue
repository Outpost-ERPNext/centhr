<template>
	<Dialog v-model:open="open" title="Mark attendance" size="lg">
		<div class="flex flex-col gap-4">
			<p class="text-[13px] text-ch-ink-3">
				Pick the days to mark. Attendance is created and submitted for each picked day; days that already have
				attendance are skipped.
			</p>
			<div v-if="!employees.length">
				<LinkField v-model="employee" doctype="Employee" label="Employee" :filters="{ status: 'Active' }" required size="md" />
			</div>
			<p v-else class="text-[13px] text-ch-ink">
				{{ employees.length }} employee{{ employees.length === 1 ? "" : "s" }} selected in the register.
			</p>

			<div v-if="targets.length && ready" class="flex flex-col gap-2">
				<div class="flex flex-wrap items-center justify-between gap-2">
					<PayrollCycleNav :key="navKey" v-model:from="fromDate" v-model:to="toDate" :company="company" />
					<div class="flex items-center gap-1">
						<Button size="sm" variant="ghost" label="All unmarked" :disabled="loadingDays" @click="selectWorkingDays" />
						<Button size="sm" variant="ghost" label="Clear" :disabled="!picked.length" @click="picked = []" />
					</div>
				</div>

				<div class="rounded-4 border border-ch-line p-2" :class="loadingDays ? 'opacity-60' : ''">
					<div class="grid grid-cols-7 gap-1 pb-1 text-center text-[11px] text-ch-ink-3">
						<span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
					</div>
					<div class="grid grid-cols-7 gap-1" role="group" aria-label="Days to mark">
						<span v-for="n in leadingBlanks" :key="`blank-${n}`" />
						<button
							v-for="d in days"
							:key="d.date"
							type="button"
							class="flex h-10 flex-col items-center justify-center rounded-3 text-[12.5px] tabular-nums transition-colors"
							:class="dayClass(d)"
							:disabled="!d.selectable"
							:aria-pressed="d.selectable ? picked.includes(d.date) : undefined"
							:aria-label="`${formatDateShort(d.date)}${d.note ? ` (${d.note})` : ''}`"
							:title="d.note || undefined"
							@click="togglePick(d.date)"
						>
							<span>{{ Number(d.date.slice(8)) }}</span>
							<span v-if="d.code" class="text-[9.5px] font-semibold leading-none">{{ d.code }}</span>
							<span v-else-if="d.somePending" class="mt-0.5 size-1.5 rounded-full bg-ch-blue-dot" />
						</button>
					</div>
				</div>
				<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ch-ink-3">
					<span class="text-ch-ink">{{ picked.length }} day{{ picked.length === 1 ? "" : "s" }} picked</span>
					<span class="flex items-center gap-1.5"><span class="size-3 rounded-[3px] bg-ch-weekend" /> Holiday or weekly off</span>
					<span class="flex items-center gap-1.5"><span class="size-3 rounded-[3px] bg-ch-subtle" /> Already marked</span>
					<span class="flex items-center gap-1.5"><span class="size-3 rounded-[3px] bg-ch-blue-bg" /> {{ PENDING_LEAVE.label }}</span>
				</div>
			</div>
			<p v-else-if="!targets.length" class="text-[13px] text-ch-ink-3">Pick an employee to see their days.</p>

			<Select v-model="status" label="Status" :options="statusOptions" size="md" />
			<ErrorMessage v-if="error" :message="error" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="open = false" />
				<Button
					variant="solid"
					:label="picked.length ? `Mark ${picked.length} day${picked.length === 1 ? '' : 's'}` : 'Mark attendance'"
					:loading="busy"
					:disabled="!canRun"
					@click="run"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, ErrorMessage, Select, toast } from "frappe-ui"
import LinkField from "@/components/fields/LinkField.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import { api, errorMessage } from "@/data/api"
import { getList } from "@/data/list"
import { getPayrollCycle } from "@/data/payroll"
import { selectOptions } from "@/data/meta"
import { addDays, formatDateShort, parseDate, today } from "@/utils/format"
import { getPendingLeaves, type PendingLeave } from "@/data/leave"
import { ATTENDANCE_CODES, ATTENDANCE_SUMMARY_STATUSES, PENDING_LEAVE } from "@/utils/status"

const props = defineProps<{
	employees: string[]
	range?: { from: string; to: string; company?: string | null } | null
}>()
const emit = defineEmits<{ done: [] }>()
const open = defineModel<boolean>({ default: false })

const ATT = "hrms.hr.doctype.attendance.attendance"
const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
/** Limits of centhr.api.attendance.get_holidays_for_employees. */
const HOLIDAY_BATCH = 50
const MAX_DAYS = 62

const todayDate = today()
const employee = ref<string | null>(null)
const company = ref<string | null>(null)
const fromDate = ref("")
const toDate = ref("")
/** The calendar shows once the company and period are known. */
const ready = ref(false)
/** Remounts the period nav for each new starting range, so it keeps that range instead of jumping to today. */
const navKey = ref(0)
const status = ref("Present")
const picked = ref<string[]>([])
const busy = ref(false)
const loadingDays = ref(false)
const error = ref("")

interface EmployeeSpan {
	name: string
	date_of_joining: string | null
	relieving_date: string | null
}
const spans = ref<EmployeeSpan[]>([])
/** Existing attendance (draft or submitted) per `employee|date`. */
const marked = ref<Record<string, string>>({})
/** Holiday dates per employee. */
const holidays = ref<Record<string, Record<string, boolean>>>({})
/** Leave applied for but not approved yet, per `employee|date`. Those days are left for the leave approval. */
const pendingLeaves = ref<Record<string, PendingLeave>>({})

// On Leave needs a leave type, which this quick form does not ask for
const statusOptions = computed(() =>
	selectOptions("Attendance", "status").filter((s) => ATTENDANCE_SUMMARY_STATUSES.includes(s) && s !== "On Leave")
)
const targets = computed(() => (props.employees.length ? props.employees : employee.value ? [employee.value] : []))
const canRun = computed(() => targets.value.length > 0 && picked.value.length > 0 && !loadingDays.value)

const employed = (e: EmployeeSpan, date: string) =>
	(!e.date_of_joining || e.date_of_joining <= date) && (!e.relieving_date || date <= e.relieving_date)
/** Employees that can still get attendance on this day: not marked yet and no leave waiting for approval. */
const openFor = (date: string) =>
	spans.value.filter(
		(e) => employed(e, date) && !marked.value[`${e.name}|${date}`] && !pendingLeaves.value[`${e.name}|${date}`]
	)

interface Day {
	date: string
	selectable: boolean
	holiday: boolean
	marked: boolean
	/** Leave is pending approval for every employee who is not already marked. */
	pending: boolean
	/** Leave is pending for some of the employees; they are skipped on this day. */
	somePending: boolean
	code: string
	note: string
}

const days = computed<Day[]>(() => {
	if (!fromDate.value || !toDate.value || toDate.value < fromDate.value) return []
	const out: Day[] = []
	for (let d = fromDate.value; d <= toDate.value && out.length <= MAX_DAYS; d = addDays(d, 1)) {
		const working = spans.value.filter((e) => employed(e, d))
		const free = openFor(d)
		const holiday = working.length > 0 && working.every((e) => d in (holidays.value[e.name] || {}))
		const markedCount = working.filter((e) => marked.value[`${e.name}|${d}`]).length
		const leaves = working.map((e) => pendingLeaves.value[`${e.name}|${d}`]).filter(Boolean)
		const isMarked = working.length > 0 && markedCount === working.length
		const pending = working.length > 0 && free.length === 0 && leaves.length > 0 && !isMarked
		// With one employee the cell shows the existing status
		const existing = spans.value.length === 1 ? marked.value[`${spans.value[0].name}|${d}`] : ""
		let note = ""
		if (d > todayDate) note = leaves.length ? `Future date · ${pendingNote(leaves, working.length)}` : "Future date"
		else if (!working.length) note = "Not employed on this day"
		else if (isMarked)
			note = `${existing ? `Already marked ${existing}` : "Already marked"}${leaves.length ? ` · ${pendingNote(leaves, working.length)}` : ""}`
		else if (leaves.length) note = pendingNote(leaves, working.length)
		else if (free.length < working.length) note = `Already marked for ${markedCount} of ${working.length}`
		else if (holiday) note = "Holiday or weekly off"
		out.push({
			date: d,
			selectable: d <= todayDate && free.length > 0,
			holiday,
			marked: isMarked,
			pending,
			somePending: leaves.length > 0 && !pending && !isMarked,
			// An Absent day under a pending leave reads PLA, as in the register
			code:
				pending || (existing === "Absent" && leaves.length)
					? PENDING_LEAVE.code
					: existing
						? ATTENDANCE_CODES[existing] || "?"
						: "",
			note,
		})
	}
	return out
})

function pendingNote(leaves: PendingLeave[], employees: number) {
	if (employees === 1) return `${PENDING_LEAVE.label} (${leaves[0].name}, ${leaves[0].leave_type})`
	return `Pending leave for ${leaves.length} of ${employees}`
}

const leadingBlanks = computed(() => (fromDate.value ? parseDate(fromDate.value)!.getDay() : 0))

function dayClass(d: Day) {
	if (d.selectable && picked.value.includes(d.date)) return "bg-ch-primary text-ch-on-primary"
	if (d.marked) return "bg-ch-subtle text-ch-ink-3"
	if (d.pending) return "bg-ch-blue-bg text-ch-blue-ink"
	if (!d.selectable) return "text-ch-ink-4"
	return d.holiday ? "bg-ch-weekend text-ch-ink-2 hover:bg-ch-hover" : "border border-ch-line text-ch-ink hover:bg-ch-hover"
}

function togglePick(date: string) {
	picked.value = picked.value.includes(date) ? picked.value.filter((d) => d !== date) : [...picked.value, date]
}

/** Every open day up to today that is not a holiday: what marking a whole period used to do. */
function selectWorkingDays() {
	picked.value = days.value.filter((d) => d.selectable && !d.holiday).map((d) => d.date)
}

function startAt(from: string, to: string, companyName: string | null) {
	company.value = companyName
	fromDate.value = from
	toDate.value = to
	navKey.value++
	ready.value = true
}

let requestId = 0
async function loadDays() {
	const names = targets.value
	if (!names.length || !fromDate.value || !toDate.value) return
	const id = ++requestId
	loadingDays.value = true
	try {
		const range = [fromDate.value, toDate.value]
		const batches: string[][] = []
		for (let i = 0; i < names.length; i += HOLIDAY_BATCH) batches.push(names.slice(i, i + HOLIDAY_BATCH))
		const [emps, rows, holidayMaps, pendingMap] = await Promise.all([
			getList<EmployeeSpan>({
				doctype: "Employee",
				fields: ["name", "date_of_joining", "relieving_date"],
				filters: [["name", "in", names]],
				limit: 0,
			}),
			getList<{ employee: string; attendance_date: string; status: string }>({
				doctype: "Attendance",
				fields: ["employee", "attendance_date", "status"],
				filters: [
					["employee", "in", names],
					["attendance_date", "between", range],
					["docstatus", "<", 2],
				],
				limit: 0,
			}),
			Promise.all(
				batches.map((batch) =>
					api<Record<string, Record<string, boolean>>>(
						"centhr.api.attendance.get_holidays_for_employees",
						{ employees: batch, from_date: range[0], to_date: range[1] },
						{ silent: true }
					).catch(() => ({}))
				)
			),
			getPendingLeaves(names, range[0], range[1]),
		])
		if (id !== requestId) return
		spans.value = emps
		marked.value = Object.fromEntries(rows.map((r) => [`${r.employee}|${r.attendance_date}`, r.status]))
		holidays.value = Object.assign({}, ...holidayMaps)
		pendingLeaves.value = pendingMap
		selectWorkingDays()
	} catch (e) {
		if (id === requestId) error.value = errorMessage(e)
	} finally {
		if (id === requestId) loadingDays.value = false
	}
}

// Days start on the payroll period on screen in the register, or the picked employee's company's current one
watch(open, (value) => {
	if (!value) return
	error.value = ""
	picked.value = []
	if (props.range) startAt(props.range.from, props.range.to, props.range.company || null)
	else if (!props.employees.length && employee.value) applyEmployeePeriod(employee.value)
})

watch(employee, (value) => {
	if (value && !props.employees.length) applyEmployeePeriod(value)
})

async function applyEmployeePeriod(name: string) {
	ready.value = false
	const row = await api<{ company?: string }>(
		"frappe.client.get_value",
		{ doctype: "Employee", filters: name, fieldname: "company" },
		{ silent: true }
	).catch(() => null)
	const cycle = await getPayrollCycle(row?.company, todayDate)
	if (employee.value === name) startAt(cycle.from_date, cycle.to_date, row?.company || null)
}

watch(
	() => (open.value ? `${targets.value.join(",")}|${fromDate.value}|${toDate.value}` : ""),
	(key) => {
		if (key) loadDays()
	}
)

async function run() {
	busy.value = true
	error.value = ""
	let count = 0
	const failed: string[] = []
	try {
		for (const emp of targets.value) {
			// Only the picked days this employee can still get attendance on
			const span = spans.value.find((e) => e.name === emp)
			const days = [...picked.value].sort().filter((d) => !!span && openFor(d).includes(span))
			if (!days.length) continue
			try {
				await api(`${ATT}.mark_bulk_attendance`, {
					data: { employee: emp, unmarked_days: days, status: status.value },
				}, { silent: true })
				count += days.length
			} catch (e) {
				failed.push(`${emp}: ${errorMessage(e)}`)
			}
		}
		if (failed.length) error.value = failed.join("\n")
		if (count) toast.success(`Marked ${count} day${count === 1 ? "" : "s"} as ${status.value}`)
		else if (!failed.length) toast.info("The picked days are already marked")
		emit("done")
		if (!failed.length) open.value = false
		else loadDays()
	} finally {
		busy.value = false
	}
}
</script>
