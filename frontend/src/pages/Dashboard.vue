<template>
	<PageHeader :crumbs="[{ label: 'Dashboard' }]" />

	<div class="flex-1 overflow-y-auto">
		<div class="mx-auto flex max-w-[1240px] flex-col gap-5 p-4 sm:p-5">
			<div>
				<h1 class="text-[18px] font-semibold tracking-[-0.01em] text-ch-ink">{{ greeting }}, {{ firstName }}</h1>
				<p class="mt-0.5 text-[13px] text-ch-ink-3">{{ scopeLine }}</p>
			</div>

			<div class="grid grid-cols-2 overflow-hidden rounded-5 border border-ch-line sm:grid-cols-3 xl:grid-cols-5">
				<RouterLink
					v-for="tile in tiles"
					:key="tile.label"
					:to="tile.route"
					class="group flex flex-col gap-1 border-b border-r border-ch-line p-4 hover:bg-ch-hover"
				>
					<span class="flex items-center gap-2 text-[13px] text-ch-ink-3">
						<span class="size-4" :class="tile.icon" />
						{{ tile.label }}
						<span class="lucide-arrow-right ml-auto size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
					</span>
					<span class="text-[24px] font-semibold tabular-nums text-ch-ink">{{ tile.value ?? "—" }}</span>
					<span class="truncate text-[12px] text-ch-ink-3">{{ tile.sub }}</span>
				</RouterLink>
			</div>

			<div class="grid grid-cols-1 gap-4 lg:grid-cols-2">
				<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
					<div class="mb-3 flex items-center gap-2">
						<h2 class="text-[14px] font-medium text-ch-ink">Pending approvals</h2>
						<span class="rounded-full bg-ch-amber-bg px-2 text-[12px] font-medium tabular-nums text-ch-amber-ink">{{ pendingTotal }}</span>
						<RouterLink to="/leave-applications?status=Open" class="ml-auto text-[13px] text-ch-ink-3 hover:text-ch-ink">View all</RouterLink>
					</div>
					<div class="flex flex-col">
						<RouterLink
							v-for="la in pending"
							:key="la.name"
							:to="`/leave-applications/${encodeURIComponent(la.name)}`"
							class="flex items-center gap-3 border-b border-ch-line py-2.5 last:border-0 hover:bg-ch-hover"
						>
							<Avatar :label="la.employee_name" size="md" />
							<div class="min-w-0 flex-1">
								<div class="truncate text-[13.5px] font-medium text-ch-ink">{{ la.employee_name }}</div>
								<div class="truncate text-[12.5px] text-ch-ink-3">
									{{ la.leave_type }} · {{ formatDateShort(la.from_date) }} – {{ formatDateShort(la.to_date) }} ·
									{{ formatNumber(la.total_leave_days) }} d
								</div>
							</div>
							<span class="hidden shrink-0 text-[12.5px] text-ch-ink-3 sm:block">{{ la.leave_approver_name || "No approver" }}</span>
						</RouterLink>
						<p v-if="!pending.length" class="py-6 text-center text-[13px] text-ch-ink-3">Nothing waiting for a decision.</p>
					</div>
				</section>

				<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
					<h2 class="mb-4 text-[14px] font-medium text-ch-ink">Leave applications by status</h2>
					<div class="flex flex-col gap-3">
						<RouterLink
							v-for="s in leaveStatuses"
							:key="s"
							:to="`/leave-applications?status=${encodeURIComponent(s)}`"
							class="grid grid-cols-[110px_1fr_40px] items-center gap-3 text-[13px]"
						>
							<StatusBadge doctype="Leave Application" :status="s" />
							<div class="h-1.5 overflow-hidden rounded-full bg-ch-subtle">
								<div
									class="h-full rounded-full"
									:style="{
										width: `${leaveMax ? ((leaveCounts[s] || 0) / leaveMax) * 100 : 0}%`,
										background: `var(--ch-${toneFor('Leave Application', s)}-dot)`,
									}"
								/>
							</div>
							<span class="text-right tabular-nums text-ch-ink">{{ leaveCounts[s] || 0 }}</span>
						</RouterLink>
					</div>
				</section>
			</div>

			<div class="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
				<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
					<div class="mb-3 flex items-baseline justify-between">
						<h2 class="text-[14px] font-medium text-ch-ink">Attendance</h2>
						<span class="text-[12.5px] text-ch-ink-3">{{ latestDay ? formatDateShort(latestDay) : "No records" }}</span>
					</div>
					<div class="flex flex-col gap-2">
						<RouterLink
							v-for="(count, status) in attendanceCounts"
							:key="status"
							:to="`/attendance?status=${encodeURIComponent(String(status))}&date_op=%3D&date_from=${latestDay}`"
							class="flex items-center gap-2 text-[13px] hover:text-ch-ink"
						>
							<span
								class="inline-flex h-5 min-w-8 items-center justify-center rounded-[5px] px-1 text-[10.5px] font-semibold"
								:style="{
									background: `var(--ch-${toneFor('Attendance', String(status))}-bg)`,
									color: `var(--ch-${toneFor('Attendance', String(status))}-ink)`,
								}"
							>{{ ATTENDANCE_CODES[String(status)] || "?" }}</span>
							<span class="flex-1 text-ch-ink-2">{{ status }}</span>
							<span class="tabular-nums text-ch-ink">{{ count }}</span>
						</RouterLink>
						<p v-if="!Object.keys(attendanceCounts).length" class="text-[13px] text-ch-ink-3">No submitted attendance yet.</p>
					</div>
				</section>

				<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
					<h2 class="mb-3 text-[14px] font-medium text-ch-ink">Leave allocation</h2>
					<div class="flex flex-col gap-3">
						<RouterLink
							v-for="a in allocationsByType"
							:key="a.leave_type"
							:to="`/leave-allocations?leave_type=${encodeURIComponent(a.leave_type)}&state=1`"
							class="flex flex-col gap-1 text-[13px]"
						>
							<div class="flex justify-between">
								<span class="text-ch-ink">{{ a.leave_type }}</span>
								<span class="tabular-nums text-ch-ink-3">{{ formatNumber(a.taken) }} of {{ formatNumber(a.total) }} days used</span>
							</div>
							<div class="h-1.5 overflow-hidden rounded-full bg-ch-subtle">
								<div class="h-full rounded-full bg-ch-green-dot" :style="{ width: `${a.total ? Math.min(100, (a.taken / a.total) * 100) : 0}%` }" />
							</div>
						</RouterLink>
						<p v-if="!allocationsByType.length" class="text-[13px] text-ch-ink-3">No active allocations.</p>
					</div>
				</section>

				<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
					<h2 class="mb-3 text-[14px] font-medium text-ch-ink">Recent activity</h2>
					<div class="flex flex-col gap-3">
						<RouterLink
							v-for="item in recent"
							:key="item.doctype + item.name"
							:to="item.route"
							class="flex gap-2.5 text-[13px]"
						>
							<span class="mt-1.5 size-2 shrink-0 rounded-full" :style="{ background: `var(--ch-${item.tone}-dot)` }" />
							<div class="min-w-0 flex-1">
								<div class="truncate text-ch-ink">{{ item.title }}</div>
								<div class="truncate text-[12px] text-ch-ink-3">{{ item.sub }} · {{ timeAgo(item.modified) }}</div>
							</div>
						</RouterLink>
						<p v-if="!recent.length" class="text-[13px] text-ch-ink-3">No recent changes.</p>
					</div>
				</section>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Avatar } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getCount, getGroupCounts, getList } from "@/data/list"
import { can } from "@/data/permissions"
import { isHR, session } from "@/data/session"
import { formatDateShort, formatNumber, timeAgo, today } from "@/utils/format"
import { ATTENDANCE_CODES, ATTENDANCE_SUMMARY_STATUSES, toneFor, type Tone } from "@/utils/status"

const hour = new Date().getHours()
const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
const firstName = computed(() => (session.fullName || session.user || "").split(" ")[0])
const scopeLine = computed(() =>
	isHR() ? "All companies you have access to" : "Records you have access to"
)

const counts = ref<Record<string, number | null>>({})
const leaveCounts = ref<Record<string, number>>({})
const pending = ref<Record<string, any>[]>([])
const pendingTotal = ref(0)
const attendanceCounts = ref<Record<string, number>>({})
const latestDay = ref<string | null>(null)
const allocationsByType = ref<{ leave_type: string; total: number; taken: number }[]>([])
const recent = ref<{ doctype: string; name: string; title: string; sub: string; modified: string; route: string; tone: Tone }[]>([])

const leaveStatuses = ["Open", "Approved", "Rejected", "Cancelled"]
const leaveMax = computed(() => Math.max(0, ...Object.values(leaveCounts.value)))

const tiles = computed(() => [
	{ label: "Employees", icon: "lucide-users", route: "/employees?status=Active", value: counts.value.employees, sub: "Active employees" },
	{ label: "Attendance", icon: "lucide-clock", route: "/attendance", value: counts.value.attendanceToday, sub: "Marked today" },
	{ label: "Leave Application", icon: "lucide-file-text", route: "/leave-applications?status=Open", value: counts.value.openLeaves, sub: "Open applications" },
	{ label: "On leave today", icon: "lucide-calendar-days", route: `/leave-applications?status=Approved&date_op=between&date_from=${today()}&date_to=${today()}`, value: counts.value.onLeave, sub: "Approved leave covering today" },
	{ label: "Leave Allocation", icon: "lucide-calendar-plus", route: "/leave-allocations?state=1", value: counts.value.allocations, sub: "Allocations valid today" },
])

/** Each widget loads on its own and quietly stays empty if the user cannot read that DocType. */
function load() {
	const t = today()
	const safe = <T,>(p: Promise<T>, fallback: T) => p.catch(() => fallback)

	if (can("Employee").read) {
		safe(getCount("Employee", [["status", "=", "Active"]], [], true), null).then((v) => (counts.value.employees = v))
		safe(
			getList({
				doctype: "Employee",
				fields: ["name", "employee_name", "modified", "status"],
				order_by: "modified desc",
				limit: 3,
				silent: true,
			}),
			[]
		).then((rows) => addRecent("Employee", rows, (r) => r.employee_name, (r) => `Employee · ${r.status}`, "/employees", (r) => toneFor("Employee", r.status)))
	}

	if (can("Attendance").read) {
		safe(getCount("Attendance", [["attendance_date", "=", t], ["docstatus", "=", 1]], [], true), null).then(
			(v) => (counts.value.attendanceToday = v)
		)
		safe(
			getList<{ attendance_date: string }>({
				doctype: "Attendance",
				fields: ["attendance_date"],
				filters: [["docstatus", "=", 1]],
				order_by: "attendance_date desc",
				limit: 1,
				silent: true,
			}),
			[]
		).then(async (rows) => {
			latestDay.value = rows[0]?.attendance_date || null
			if (latestDay.value) {
				const byStatus = await safe(
					getGroupCounts("Attendance", "status", [["attendance_date", "=", latestDay.value], ["docstatus", "=", 1]]),
					{}
				)
				attendanceCounts.value = Object.fromEntries(
					ATTENDANCE_SUMMARY_STATUSES.filter((s) => byStatus[s]).map((s) => [s, byStatus[s]])
				)
			}
		})
	}

	if (can("Leave Application").read) {
		safe(getGroupCounts("Leave Application", "status"), {}).then((c) => {
			leaveCounts.value = c
			counts.value.openLeaves = c.Open || 0
		})
		safe(
			getCount("Leave Application", [["status", "=", "Approved"], ["docstatus", "=", 1], ["from_date", "<=", t], ["to_date", ">=", t]], [], true),
			null
		).then((v) => (counts.value.onLeave = v))

		// Approvers see what waits on them; HR sees everything open
		const pendingFilters: [string, string, any][] = [["status", "=", "Open"], ["docstatus", "=", 0]]
		if (!isHR()) pendingFilters.push(["leave_approver", "=", session.user])
		safe(
			getList({
				doctype: "Leave Application",
				fields: ["name", "employee_name", "leave_type", "from_date", "to_date", "total_leave_days", "leave_approver_name"],
				filters: pendingFilters,
				order_by: "from_date asc",
				limit: 5,
				silent: true,
			}),
			[]
		).then((rows) => (pending.value = rows))
		safe(getCount("Leave Application", pendingFilters, [], true), 0).then((v) => (pendingTotal.value = v))
		safe(
			getList({
				doctype: "Leave Application",
				fields: ["name", "employee_name", "leave_type", "status", "modified"],
				order_by: "modified desc",
				limit: 4,
				silent: true,
			}),
			[]
		).then((rows) =>
			addRecent("Leave Application", rows, (r) => `${r.employee_name} · ${r.leave_type}`, (r) => `Leave application ${r.status.toLowerCase()}`, "/leave-applications", (r) => toneFor("Leave Application", r.status))
		)
	}

	if (can("Leave Allocation").read) {
		const active: [string, string, any][] = [["docstatus", "=", 1], ["from_date", "<=", t], ["to_date", ">=", t]]
		safe(getCount("Leave Allocation", active, [], true), null).then((v) => (counts.value.allocations = v))
		safe(
			getList<{ leave_type: string; total: number }>({
				doctype: "Leave Allocation",
				fields: ["leave_type", { SUM: "total_leaves_allocated", as: "total" }],
				filters: active,
				group_by: "leave_type",
				limit: 0,
				silent: true,
			}),
			[]
		).then(async (rows) => {
			// Days taken this period: approved leave inside the active allocations' window
			const taken = can("Leave Application").read
				? await safe(
						getList<{ leave_type: string; days: number }>({
							doctype: "Leave Application",
							fields: ["leave_type", { SUM: "total_leave_days", as: "days" }],
							filters: [["status", "=", "Approved"], ["docstatus", "=", 1], ["from_date", ">=", `${t.slice(0, 4)}-01-01`]],
							group_by: "leave_type",
							limit: 0,
							silent: true,
						}),
						[]
					)
				: []
			const takenBy = Object.fromEntries(taken.map((r) => [r.leave_type, r.days || 0]))
			allocationsByType.value = rows.map((r) => ({ leave_type: r.leave_type, total: r.total || 0, taken: takenBy[r.leave_type] || 0 }))
		})
	}
}

function addRecent(
	doctype: string,
	rows: Record<string, any>[],
	title: (r: Record<string, any>) => string,
	sub: (r: Record<string, any>) => string,
	base: string,
	tone: (r: Record<string, any>) => Tone
) {
	const items = rows.map((r) => ({
		doctype,
		name: r.name,
		title: title(r),
		sub: sub(r),
		modified: r.modified,
		route: `${base}/${encodeURIComponent(r.name)}`,
		tone: tone(r),
	}))
	recent.value = [...recent.value, ...items].sort((a, b) => (a.modified < b.modified ? 1 : -1)).slice(0, 6)
}

load()
</script>
