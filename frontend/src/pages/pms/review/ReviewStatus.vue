<template>
	<PageHeader :crumbs="[{ label: 'Form Submission Status' }]">
		<template #actions>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" :disabled="!ready" @click="load" />
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<QuarterScopeBar v-model="scope" />

		<div class="grid grid-cols-3 gap-2 px-5">
			<StatCard label="Reviews asked for" :value="formatNumber(rows.length)" :loading="loading" />
			<StatCard label="Submitted" :value="formatNumber(count('Completed'))" tone="green" :active="status === 'Completed'" :loading="loading" clickable @click="toggleStatus('Completed')" />
			<StatCard label="Pending" :value="formatNumber(count('Pending'))" tone="amber" :active="status === 'Pending'" :loading="loading" clickable @click="toggleStatus('Pending')" />
		</div>

		<FilterBar v-model:search="search" :total="shown.length" :active="!!search || !!status" search-placeholder="Search employee or reviewer" noun="review" @clear="clearFilters" />

		<DataTable
			:columns="columns"
			:rows="shown"
			:loading="loading"
			:error="error"
			:clickable="false"
			:show-clear="!!search || !!status"
			empty-icon="lucide-clipboard-check"
			:empty-message="rows.length ? 'No reviews match these filters' : 'No reviews asked for in this quarter yet'"
			mobile-aside="status"
			@clear-filters="clearFilters"
		>
			<template #cell-status="{ row }">
				<StatusBadge :tone="row.status === 'Completed' ? 'green' : 'amber'" :status="row.status === 'Completed' ? 'Submitted' : 'Pending'" />
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import QuarterScopeBar from "./QuarterScopeBar.vue"
import { getReviewStatus, type QuarterScope, type ReviewRow } from "@/data/pmsReview"
import { formatDateShort, formatNumber } from "@/utils/format"

const scope = ref<QuarterScope>({ fiscalYear: "", quarter: "", company: "", department: "" })
const ready = computed(() => !!scope.value.fiscalYear && !!scope.value.quarter)

const rows = ref<ReviewRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref("")
const status = ref("")
let requestId = 0

async function load() {
	if (!ready.value) return
	const id = ++requestId
	loading.value = true
	error.value = null
	try {
		const data = await getReviewStatus(scope.value)
		if (id === requestId) rows.value = data
	} catch (e: any) {
		if (id === requestId) error.value = e?.messages?.[0] || "Could not load the reviews"
	} finally {
		if (id === requestId) loading.value = false
	}
}
watch(scope, load, { deep: true })

const count = (value: string) => rows.value.filter((row) => row.status === value).length
const shown = computed(() => {
	const text = search.value.trim().toLowerCase()
	return rows.value.filter(
		(row) => (!status.value || row.status === status.value) && (!text || `${row.reviewee_name} ${row.reviewer_name}`.toLowerCase().includes(text))
	)
})

function toggleStatus(value: string) {
	status.value = status.value === value ? "" : value
}
function clearFilters() {
	search.value = ""
	status.value = ""
}

const columns: Column[] = [
	{ key: "reviewee_name", label: "Employee", width: "minmax(180px,1.6fr)" },
	{ key: "reviewer_name", label: "Reviewer", width: "minmax(180px,1.6fr)" },
	{ key: "relationship_type", label: "Reviews as", width: "130px", hideOnMobile: true, format: (v) => (v === "Peers" ? "Peer" : v) },
	{ key: "department", label: "Department", width: "minmax(130px,1.1fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "status", label: "Status", width: "120px" },
	{ key: "review_date", label: "Submitted on", width: "130px", hideOnMobile: true, format: (v) => (v ? formatDateShort(v) : "—") },
]
</script>
