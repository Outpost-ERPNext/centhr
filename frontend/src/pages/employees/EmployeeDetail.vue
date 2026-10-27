<template>
	<DocPageShell
		doctype="Employee"
		list-label="Employees"
		:page="page"
		:title="page.doc.value.employee_name"
		:subtitle="subtitle"
		:link-filters="linkFilters"
		:link-queries="linkQueries"
		:required-fields="syncRequired"
		show-empty
		@change="onChange"
	>
		<template v-if="page.editing.value && syncRequired.length" #notice>
			<div class="flex items-start gap-2 rounded-4 border border-ch-line bg-ch-surface px-4 py-3 text-[13px] text-ch-ink-2">
				<span class="lucide-refresh-cw mt-0.5 size-4 shrink-0 text-ch-ink-3" />
				<span>
					{{ page.doc.value.company }} syncs employees to its entity site. To send this employee there, fill in
					<span class="font-medium text-ch-ink">{{ syncRequiredLabels }}</span>.
				</span>
			</div>
		</template>

		<template #avatar>
			<Avatar
				v-if="!page.isNew"
				:image="page.doc.value.image || undefined"
				:label="page.doc.value.employee_name"
				size="2xl"
				shape="square"
			/>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill doctype="Employee" :status="page.doc.value.status" />
		</template>

		<template #tab-attendance_and_leave_details="{ tab }">
			<div class="flex flex-col gap-6">
				<div>
					<h3 class="mb-3 text-[13px] font-medium text-ch-ink-2">Leave balance</h3>
					<div v-if="balances.length" class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-2">
						<div v-for="b in balances" :key="b.type" class="rounded-4 border border-ch-line p-3">
							<div class="truncate text-[13px] text-ch-ink-2">{{ b.type }}</div>
							<div class="mt-1 text-[20px] font-semibold tabular-nums text-ch-ink">
								{{ formatNumber(b.remaining_leaves) }}
								<span class="text-[12px] font-normal text-ch-ink-3">of {{ formatNumber(b.total_leaves) }} days left</span>
							</div>
							<div class="mt-2 h-1.5 overflow-hidden rounded-full bg-ch-subtle">
								<div
									class="h-full rounded-full bg-ch-green-dot"
									:style="{ width: `${b.total_leaves ? Math.min(100, (b.remaining_leaves / b.total_leaves) * 100) : 0}%` }"
								/>
							</div>
							<div class="mt-2 text-[12px] text-ch-ink-3">
								Taken {{ formatNumber(b.leaves_taken) }} · Pending {{ formatNumber(b.leaves_pending_approval) }}
							</div>
						</div>
					</div>
					<p v-else class="text-[13px] text-ch-ink-3">No leave allocated for today's date.</p>
				</div>

				<div>
					<div class="mb-3 flex items-center justify-between">
						<h3 class="text-[13px] font-medium text-ch-ink-2">Attendance this month</h3>
						<RouterLink :to="`/attendance?employee=${encodeURIComponent(page.doc.value.name)}`" class="text-[13px] text-ch-ink-3 hover:text-ch-ink">
							View all
						</RouterLink>
					</div>
					<div class="flex flex-wrap gap-2">
						<div
							v-for="(count, status) in attendanceCounts"
							:key="status"
							class="flex items-center gap-2 rounded-4 border border-ch-line px-3 py-2 text-[13px]"
						>
							<StatusBadge doctype="Attendance" :status="String(status)" />
							<span class="font-semibold tabular-nums">{{ count }}</span>
						</div>
						<p v-if="!Object.keys(attendanceCounts).length" class="text-[13px] text-ch-ink-3">
							No submitted attendance this month.
						</p>
					</div>
				</div>

				<div>
					<div class="mb-3 flex items-center justify-between">
						<h3 class="text-[13px] font-medium text-ch-ink-2">Recent leave applications</h3>
						<RouterLink :to="`/leave-applications?employee=${encodeURIComponent(page.doc.value.name)}`" class="text-[13px] text-ch-ink-3 hover:text-ch-ink">
							View all
						</RouterLink>
					</div>
					<div class="flex flex-col">
						<RouterLink
							v-for="la in leaveApplications"
							:key="la.name"
							:to="`/leave-applications/${encodeURIComponent(la.name)}`"
							class="flex items-center gap-3 border-b border-ch-line py-2 text-[13px] last:border-0 hover:bg-ch-hover"
						>
							<span class="min-w-0 flex-1 truncate">
								<span class="font-medium text-ch-ink">{{ la.leave_type }}</span>
								<span class="text-ch-ink-3"> · {{ formatDateShort(la.from_date) }} – {{ formatDateShort(la.to_date) }} · {{ formatNumber(la.total_leave_days) }} d</span>
							</span>
							<StatusBadge doctype="Leave Application" :status="la.status" />
						</RouterLink>
						<p v-if="!leaveApplications.length" class="text-[13px] text-ch-ink-3">No leave applications yet.</p>
					</div>
				</div>

				<DocDetail v-if="tab" doctype="Employee" :doc="page.doc.value" :tab="tab" show-empty />
			</div>
		</template>

		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Summary"
				:items="[
					{ label: 'Designation', value: page.doc.value.designation },
					{ label: 'Department', value: page.doc.value.department },
					{ label: 'Company', value: page.doc.value.company },
					{
						label: 'Reports to',
						value: reportsToName || page.doc.value.reports_to,
						route: routeFor('Employee', page.doc.value.reports_to),
					},
					{ label: 'Date of joining', value: formatDate(page.doc.value.date_of_joining) },
					{ label: 'User', value: page.doc.value.user_id },
				]"
			/>
			<section v-if="syncStatus.length" class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Entity sync</h3>
				<div v-for="s in syncStatus" :key="s.company" class="flex flex-col gap-1 text-[13px]">
					<div class="flex items-center justify-between gap-2">
						<span class="truncate text-ch-ink-2">{{ s.company }}</span>
						<Badge :theme="SYNC_TONES[s.status] || 'gray'" :label="s.status" />
					</div>
					<p v-if="s.creation" class="text-[12px] text-ch-ink-3">Last attempt {{ timeAgo(s.creation) }}</p>
					<p v-if="s.status === 'Failed' && s.error" class="text-[12px] text-ch-red-ink">{{ s.error }}</p>
				</div>
			</section>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Connections</h3>
				<div class="flex flex-col gap-1">
					<RouterLink
						v-for="c in connections"
						:key="c.label"
						:to="c.route"
						class="flex items-center justify-between rounded-3 px-2 py-1.5 text-[13px] hover:bg-ch-subtle"
					>
						<span class="flex items-center gap-2 text-ch-ink-2"><span class="size-4" :class="c.icon" />{{ c.label }}</span>
						<span class="rounded-full bg-ch-subtle px-2 text-[12px] tabular-nums text-ch-ink-2">{{ c.count }}</span>
					</RouterLink>
				</div>
			</section>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Avatar, Badge, toast } from "frappe-ui"
import DocPageShell from "@/components/DocPageShell.vue"
import DocDetail from "@/components/DocDetail.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { api } from "@/data/api"
import { getCount, getGroupCounts, getList } from "@/data/list"
import { getMeta } from "@/data/meta"
import { formatDate, formatDateShort, formatNumber, timeAgo, toISODate, today } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()

interface Balance {
	type: string
	total_leaves: number
	remaining_leaves: number
	leaves_taken: number
	leaves_pending_approval: number
}

const balances = ref<Balance[]>([])
const attendanceCounts = ref<Record<string, number>>({})
const leaveApplications = ref<Record<string, any>[]>([])
const reportsToName = ref("")
const connections = ref<{ label: string; icon: string; route: string; count: number }[]>([])

const syncRequired = ref<string[]>([])
const syncStatus = ref<{ company: string; status: string; error?: string; creation?: string }[]>([])
const SYNC_TONES: Record<string, "green" | "red" | "orange" | "gray"> = {
	Success: "green",
	Failed: "red",
	Pending: "orange",
}

const page = useDocPage("Employee", props.name, {
	onLoaded: loadExtras,
	requiredFields: () => syncRequired.value,
})

const syncRequiredLabels = computed(() =>
	syncRequired.value
		.map((f) => getMeta("Employee")?.fields.find((df) => df.fieldname === f)?.label || f)
		.join(", ")
)

/** The company's entity site rejects employees without these fields (centhr.api.post.employee). */
watch(
	() => [page.editing.value, page.doc.value.company] as const,
	async ([editing, company], _old, onCleanup) => {
		let stale = false
		onCleanup(() => (stale = true))
		if (!editing || !company) {
			syncRequired.value = []
			return
		}
		const res = await api<{ required_fields: string[] }>(
			"centhr.api.employee.get_entity_sync_requirements",
			{ company },
			{ silent: true }
		).catch(() => ({ required_fields: [] }))
		if (!stale) syncRequired.value = res.required_fields
	},
	{ immediate: true }
)

const subtitle = computed(() =>
	page.isNew ? "" : [page.doc.value.designation, page.doc.value.department].filter(Boolean).join(" · ")
)

/** Mirrors centhr/public/js/employee.js: managers come from the cross company when it is set. */
const linkQueries = {
	reports_to: "erpnext.controllers.queries.employee_query",
	user_id: "frappe.core.doctype.user.user.user_query",
}

/** Company-scoped masters, as in the ERPNext and HRMS Employee forms. */
const linkFilters = {
	department: (doc: Record<string, any>) => (doc.company ? { company: doc.company } : undefined),
	cost_center: (doc: Record<string, any>) => (doc.company ? { company: doc.company } : undefined),
	payroll_cost_center: (doc: Record<string, any>) =>
		doc.company ? { company: doc.company, is_group: 0 } : undefined,
	user_id: () => ({ ignore_user_type: 1 }),
	reports_to: (doc: Record<string, any>) => {
		const filters: Record<string, any> = { status: "Active" }
		if (doc.name && !doc.__islocal) filters.name = ["!=", doc.name]
		if (doc.cross_company_reports && doc.cross_company) filters.company = doc.cross_company
		return filters
	},
}

function onChange(fieldname: string, value: any) {
	const doc = page.doc.value
	if (fieldname === "cross_company") {
		if (value && value === doc.company) {
			toast.error("Employee Company and Cross Reporting Company cannot be the same")
			doc.cross_company = null
		}
		doc.reports_to = null
	}
	if (fieldname === "company") {
		// Company-scoped masters from another company would fail validation or sync
		for (const f of ["department", "cost_center", "payroll_cost_center"]) doc[f] = null
		if (doc.cross_company && doc.cross_company === value) {
			doc.cross_company = null
			doc.reports_to = null
		}
	}
	if (fieldname === "cross_company_reports") {
		if (!value) doc.cross_company = null
		doc.reports_to = null
	}
}

async function loadExtras(doc: Record<string, any>) {
	if (page.isNew || !doc.name) return
	const employee = doc.name
	const monthStart = toISODate(new Date(new Date().getFullYear(), new Date().getMonth(), 1))

	const tasks: Promise<unknown>[] = [
		api("hrms.hr.doctype.leave_application.leave_application.get_leave_details", { employee, date: today() }, { silent: true })
			.then((res: any) => {
				balances.value = Object.entries(res?.leave_allocation || {}).map(([type, b]: [string, any]) => ({ type, ...b }))
			})
			.catch(() => (balances.value = [])),
		getGroupCounts("Attendance", "status", [
			["employee", "=", employee],
			["docstatus", "=", 1],
			["attendance_date", ">=", monthStart],
		]).then((counts) => (attendanceCounts.value = counts)),
		getList({
			doctype: "Leave Application",
			fields: ["name", "leave_type", "from_date", "to_date", "total_leave_days", "status"],
			filters: [["employee", "=", employee]],
			order_by: "from_date desc",
			limit: 5,
			silent: true,
		}).then((rows) => (leaveApplications.value = rows)),
		api<typeof syncStatus.value>("centhr.api.employee.get_entity_sync_status", { employee }, { silent: true })
			.then((rows) => (syncStatus.value = rows || []))
			.catch(() => (syncStatus.value = [])),
		Promise.all([
			getCount("Leave Application", [["employee", "=", employee]], [], true).catch(() => 0),
			getCount("Leave Allocation", [["employee", "=", employee]], [], true).catch(() => 0),
			getCount("Attendance", [["employee", "=", employee]], [], true).catch(() => 0),
		]).then(([apps, allocs, att]) => {
			const q = `?employee=${encodeURIComponent(employee)}`
			connections.value = [
				{ label: "Leave Applications", icon: "lucide-file-text", route: `/leave-applications${q}`, count: apps },
				{ label: "Leave Allocations", icon: "lucide-calendar-plus", route: `/leave-allocations${q}`, count: allocs },
				{ label: "Attendance", icon: "lucide-clock", route: `/attendance${q}`, count: att },
			]
		}),
	]
	if (doc.reports_to) {
		tasks.push(
			getList({ doctype: "Employee", fields: ["employee_name"], filters: [["name", "=", doc.reports_to]], limit: 1, silent: true })
				.then((rows) => (reportsToName.value = rows[0]?.employee_name || ""))
				.catch(() => undefined)
		)
	}
	await Promise.allSettled(tasks)
}
</script>
