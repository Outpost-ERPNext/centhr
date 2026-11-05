<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
			<StatCard
				v-for="card in cards"
				:key="card.key"
				clickable
				:active="view === card.key"
				:label="card.label"
				:value="formatNumber(card.value)"
				:sub="card.sub"
				:tone="card.tone"
				:loading="loading"
				@click="view = view === card.key ? 'all' : card.key"
			/>
		</div>
		<p class="text-[12.5px] text-ch-ink-3">
			Working days leave out holidays and days before joining or after leaving. Unmarked days are past working days with no
			attendance; payroll pays them only once attendance is marked.
		</p>
	</div>

	<FilterBar v-model:search="search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="employee" @clear="clear">
		<FilterLink v-model="department" doctype="Department" placeholder="Department" :filters="scope.company ? { company: scope.company } : undefined" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:show-clear="hasFilters"
		empty-icon="lucide-calendar-check"
		empty-message="No employees match these filters"
		mobile-aside="paid_days"
		min-width="1080px"
		@row-click="(row) => router.push({ path: '/attendance', query: { employee: row.name } })"
		@clear-filters="clear"
	>
		<template #cell-name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }}{{ row.department ? ` · ${row.department}` : "" }}</div>
			</div>
		</template>
		<template #cell-absent="{ row }">
			<span :class="row.absent ? 'font-medium text-ch-red-ink' : 'text-ch-ink-3'">{{ formatNumber(row.absent) }}</span>
		</template>
		<template #cell-unpaid_leave="{ row }">
			<span :class="row.unpaid_leave ? 'font-medium text-ch-amber-ink' : 'text-ch-ink-3'">{{ formatNumber(row.unpaid_leave) }}</span>
		</template>
		<template #cell-unmarked="{ row }">
			<span :class="row.unmarked ? 'font-medium text-ch-amber-ink' : 'text-ch-ink-3'">{{ formatNumber(row.unmarked) }}</span>
		</template>
		<template #cell-paid_days="{ row }">
			<span class="font-medium text-ch-green-ink">{{ formatNumber(row.paid_days) }}</span>
		</template>
		<template #cell-slip_status="{ row }">
			<StatusBadge v-if="row.slip_status" pill doctype="Salary Slip" :status="row.slip_status" />
			<span v-else class="text-ch-ink-3">—</span>
		</template>
	</DataTable>
	<Pager v-model:page="page" v-model:page-size="pageSize" :total="filtered.length" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import Pager from "@/components/Pager.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getAttendance, useTabData, type Scope } from "@/data/payrollDashboard"
import { formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"

const props = defineProps<{ scope: Scope }>()
const router = useRouter()
const { data, loading, error } = useTabData(props.scope, getAttendance)

type Row = NonNullable<typeof data.value>[number]
const sum = (key: string) => (data.value || []).reduce((total, r) => total + (r[key] || 0), 0)
// Each card also filters the table to the employees it counts
const FILTERS: Record<string, (r: Row) => boolean> = {
	all: () => true,
	absent: (r) => r.absent > 0,
	unpaid_leave: (r) => r.unpaid_leave > 0,
	unmarked: (r) => r.unmarked > 0,
	paid_leave: (r) => r.paid_leave > 0,
	complete: (r) => !r.absent && !r.unmarked && !r.unpaid_leave,
}

const cards = computed<{ key: string; label: string; value: number; sub: string; tone?: Tone }[]>(() => [
	{ key: "all", label: "Employees", value: data.value?.length || 0, sub: `${formatNumber(sum("working_days"))} working days` },
	{ key: "complete", label: "Full attendance", value: count("complete"), sub: "No absence, LWP or gaps", tone: "green" },
	{ key: "absent", label: "Absent", value: sum("absent"), sub: `${count("absent")} employees`, tone: "red" },
	{ key: "unpaid_leave", label: "Leave without pay", value: sum("unpaid_leave"), sub: `${count("unpaid_leave")} employees`, tone: "amber" },
	{ key: "paid_leave", label: "Paid leave", value: sum("paid_leave"), sub: `${count("paid_leave")} employees`, tone: "blue" },
	{ key: "unmarked", label: "Unmarked", value: sum("unmarked"), sub: `${count("unmarked")} employees`, tone: "amber" },
])

const view = ref("all")
const search = ref("")
const department = ref("")
const page = ref(1)
const pageSize = ref(20)

const filtered = computed(() => {
	const term = search.value.trim().toLowerCase()
	return (data.value || [])
		.filter(FILTERS[view.value])
		.filter((r) => !term || r.name.toLowerCase().includes(term) || (r.employee_name || "").toLowerCase().includes(term))
		.filter((r) => !department.value || r.department === department.value)
})
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const hasFilters = computed(() => !!(search.value || department.value || view.value !== "all"))
watch([view, search, department, pageSize], () => (page.value = 1))

function count(key: string) {
	return (data.value || []).filter(FILTERS[key]).length
}

function clear() {
	search.value = department.value = ""
	view.value = "all"
}

const days = (label: string, key: string): Column => ({ key, label, width: "74px", align: "right", format: (v) => formatNumber(v) })
const columns: Column[] = [
	{ key: "name", label: "Employee", width: "minmax(200px,2fr)" },
	days("Working", "working_days"),
	days("Present", "present"),
	days("WFH", "work_from_home"),
	days("Half day", "half_day"),
	days("Paid leave", "paid_leave"),
	days("LWP", "unpaid_leave"),
	days("Absent", "absent"),
	days("Unmarked", "unmarked"),
	days("Paid days", "paid_days"),
	{ key: "slip_status", label: "Salary slip", width: "110px" },
]
</script>
