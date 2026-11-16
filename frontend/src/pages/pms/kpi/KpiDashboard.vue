<template>
	<PageHeader :crumbs="[{ label: 'KPI Dashboard' }]">
		<template #actions>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" :disabled="!ready" @click="load" />
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<KpiScopeBar v-model="scope" />

		<div class="grid grid-cols-2 gap-2 px-5 xl:grid-cols-4">
			<StatCard label="Employees with KPIs" :value="formatNumber(rows.length)" :loading="loading" />
			<StatCard
				v-for="stage in STAGE_KEYS"
				:key="stage"
				:label="KPI_STAGES[stage].label"
				:value="formatNumber(counts[stage])"
				:tone="KPI_STAGES[stage].tone"
				:sub="stage === 'done' && counts.done ? `Average score ${formatNumber(averageScore, 2)}` : undefined"
				:active="stageFilter === stage"
				:loading="loading"
				clickable
				@click="stageFilter = stageFilter === stage ? '' : stage"
			/>
		</div>

		<FilterBar v-model:search="search" :total="shown.length" :active="!!search || !!stageFilter" search-placeholder="Search employees" noun="employee" @clear="clearFilters" />

		<DataTable
			:columns="columns"
			:rows="shown"
			:loading="loading"
			:error="error"
			:show-clear="!!search || !!stageFilter"
			empty-icon="lucide-target"
			:empty-message="emptyMessage"
			mobile-aside="stage"
			@row-click="open"
			@clear-filters="clearFilters"
		>
			<template #cell-employee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.designation].filter(Boolean).join(" · ") }}</div>
				</div>
			</template>
			<template #cell-stage="{ row }">
				<StatusBadge :tone="KPI_STAGES[kpiStage(row as KpiRow)].tone" :status="KPI_STAGES[kpiStage(row as KpiRow)].label" />
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import KpiScopeBar from "./KpiScopeBar.vue"
import { getKpiDashboard, kpiStage, KPI_STAGES, type KpiRow, type KpiScope, type KpiStage } from "@/data/pms"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const STAGE_KEYS: KpiStage[] = ["template", "fill", "done"]

const router = useRouter()
const scope = ref<KpiScope>({ fiscalYear: "", month: "", company: "", department: "" })
const ready = computed(() => !!scope.value.fiscalYear && !!scope.value.month)

const rows = ref<KpiRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref("")
const stageFilter = ref<KpiStage | "">("")
let requestId = 0

async function load() {
	if (!ready.value) return
	const id = ++requestId
	loading.value = true
	error.value = null
	try {
		const data = await getKpiDashboard(scope.value)
		// A slower, older request must not overwrite a newer one
		if (id === requestId) rows.value = data
	} catch (e: any) {
		if (id === requestId) error.value = e?.messages?.[0] || "Could not load the KPIs"
	} finally {
		if (id === requestId) loading.value = false
	}
}
watch(scope, load, { deep: true })

const counts = computed(() => {
	const totals: Record<KpiStage, number> = { template: 0, fill: 0, done: 0 }
	for (const row of rows.value) totals[kpiStage(row)]++
	return totals
})
const averageScore = computed(() => {
	const done = rows.value.filter((row) => kpiStage(row) === "done")
	return done.length ? done.reduce((sum, row) => sum + (row.result?.overall_score || 0), 0) / done.length : 0
})

const shown = computed(() => {
	const text = search.value.trim().toLowerCase()
	return rows.value.filter(
		(row) =>
			(!stageFilter.value || kpiStage(row) === stageFilter.value) &&
			(!text || `${row.employee_name} ${row.employee}`.toLowerCase().includes(text))
	)
})
const emptyMessage = computed(() => {
	if (!ready.value) return "Choose a fiscal year and a month"
	return rows.value.length ? "No employees match these filters" : `No KPI Templates for ${scope.value.month} ${scope.value.fiscalYear} yet`
})

function clearFilters() {
	search.value = ""
	stageFilter.value = ""
}

/** The result once there is one to fill in or read, the template before that. */
function open(row: Record<string, any>) {
	const target = row.result ? routeFor("KPI Result", row.result.name) : routeFor("KPI Template", row.name)
	router.push(target!)
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)" },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "stage", label: "Status", width: "170px" },
	{
		key: "score",
		label: "Score",
		width: "90px",
		align: "right",
		format: (_, row) => (row.result?.docstatus === 1 || row.result?.overall_score ? formatNumber(row.result.overall_score, 2) : "—"),
	},
	{ key: "remark", label: "Remark", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (_, row) => row.result?.remark || "—" },
]
</script>
