<template>
	<PageHeader :crumbs="[{ label: 'Overall Score Dashboard' }]">
		<template #actions>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" :disabled="!ready" @click="load" />
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<QuarterScopeBar v-model="scope">
			<div class="w-[calc(50%-4px)] sm:w-36">
				<Select v-model="month" :options="monthOptions" size="sm" aria-label="Month" />
			</div>
		</QuarterScopeBar>

		<p class="px-5 text-[13px] text-ch-ink-3">
			Overall score = KPI score × KPI weight + 360 score × 360 weight, from the company's PMS Settings. It appears once an employee has both
			scores. {{ month ? `KPI score of ${month}; 360 score of ${scope.quarter}.` : `KPI score is the average of the months of ${scope.quarter}.` }}
		</p>

		<FilterBar v-model:search="search" :total="shown.length" :active="!!search" search-placeholder="Search employees" noun="employee" @clear="search = ''" />

		<DataTable
			:columns="columns"
			:rows="shown"
			row-key="employee"
			:loading="loading"
			:error="error"
			:clickable="false"
			:show-clear="!!search"
			empty-icon="lucide-gauge"
			:empty-message="rows.length ? 'No employees match this search' : 'No employees to show'"
			@clear-filters="search = ''"
		>
			<template #cell-employee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.designation].filter(Boolean).join(" · ") }}</div>
				</div>
			</template>
			<template #cell-review_score="{ row }">
				<div class="text-right">
					<div class="tabular-nums">{{ score(row.review_score) }}</div>
					<div v-if="row.reviews_total" class="text-[12px]" :class="row.reviews_done < row.reviews_total ? 'text-ch-amber-ink' : 'text-ch-ink-3'">
						{{ row.reviews_done }} of {{ row.reviews_total }} reviews
					</div>
				</div>
			</template>
			<template #cell-overall_score="{ row }">
				<span class="font-medium tabular-nums text-ch-ink">{{ score(row.overall_score) }}</span>
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Select } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import QuarterScopeBar from "../review/QuarterScopeBar.vue"
import { getOverallScores, QUARTERS, type OverallRow, type QuarterScope } from "@/data/pmsReview"
import { formatNumber } from "@/utils/format"

const scope = ref<QuarterScope>({ fiscalYear: "", quarter: "", company: "", department: "" })
const month = ref("")
const ready = computed(() => !!scope.value.fiscalYear && !!scope.value.quarter)

const monthOptions = computed(() => [
	{ label: "Whole quarter", value: "" },
	...(QUARTERS[scope.value.quarter] || []).map((m) => ({ label: m, value: m })),
])
// A month of another quarter makes no sense after the quarter changes
watch(
	() => scope.value.quarter,
	() => (month.value = "")
)

const rows = ref<OverallRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref("")
let requestId = 0

async function load() {
	if (!ready.value) return
	const id = ++requestId
	loading.value = true
	error.value = null
	try {
		const data = await getOverallScores(scope.value, month.value)
		if (id === requestId) rows.value = data
	} catch (e: any) {
		if (id === requestId) error.value = e?.messages?.[0] || "Could not load the scores"
	} finally {
		if (id === requestId) loading.value = false
	}
}
watch([scope, month], load, { deep: true })

const shown = computed(() => {
	const text = search.value.trim().toLowerCase()
	return rows.value.filter((row) => !text || `${row.employee_name} ${row.employee}`.toLowerCase().includes(text))
})

const score = (value: number | null) => (value === null || value === undefined ? "—" : formatNumber(value, 2))

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)" },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "kpi_score", label: "KPI score", width: "110px", align: "right", format: score },
	{ key: "review_score", label: "360 score", width: "140px", align: "right" },
	{ key: "overall_score", label: "Overall", width: "100px", align: "right" },
	{ key: "overall_remark", label: "Remark", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
]
</script>
