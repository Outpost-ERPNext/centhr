<template>
	<PageHeader :crumbs="[{ label: 'Form Dashboard' }]">
		<template #actions>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" :disabled="!ready" @click="load" />
			<Button
				v-if="can('PMS Questionnaire').write"
				variant="solid"
				icon-left="lucide-send"
				:label="selected.length ? `Close ${selected.length} selected` : 'Close all open'"
				:disabled="!closable.length"
				:loading="closing"
				@click="confirmClose"
			/>
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<QuarterScopeBar v-model="scope" />

		<div class="grid grid-cols-2 gap-2 px-5 xl:grid-cols-4">
			<StatCard label="Questionnaires" :value="formatNumber(rows.length)" :loading="loading" />
			<StatCard label="Open" :value="formatNumber(count('Open'))" tone="amber" :active="status === 'Open'" :loading="loading" clickable @click="toggleStatus('Open')" />
			<StatCard label="Closed and sent" :value="formatNumber(count('Completed'))" tone="green" :active="status === 'Completed'" :loading="loading" clickable @click="toggleStatus('Completed')" />
			<StatCard label="Reviews in" :value="`${formatNumber(reviewsDone)} of ${formatNumber(reviewsTotal)}`" tone="blue" :loading="loading" />
		</div>

		<FilterBar v-model:search="search" :total="shown.length" :active="!!search || !!status" search-placeholder="Search employees" noun="questionnaire" @clear="clearFilters" />

		<DataTable
			v-model:selected="selected"
			:columns="columns"
			:rows="shown"
			:loading="loading"
			:error="error"
			:selectable="can('PMS Questionnaire').write"
			:show-clear="!!search || !!status"
			empty-icon="lucide-file-question"
			:empty-message="rows.length ? 'No questionnaires match these filters' : 'No questionnaires for this quarter yet. Create them on Create PMS Form.'"
			mobile-aside="status"
			@row-click="(row) => router.push(routeFor('PMS Questionnaire', row.name)!)"
			@clear-filters="clearFilters"
		>
			<template #cell-employee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }}</div>
				</div>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge :tone="row.status === 'Open' ? 'amber' : 'green'" :status="row.status === 'Open' ? 'Open' : 'Closed and sent'" />
			</template>
		</DataTable>
	</div>

	<Dialog v-if="failed.length" :open="true" title="Some questionnaires could not be closed" size="lg" @update:open="failed = []">
		<ul class="flex flex-col gap-2 text-[13px]">
			<li v-for="item in failed" :key="item.questionnaire">
				<span class="font-medium text-ch-ink">{{ nameOf(item.questionnaire) }}</span>
				<span class="block text-ch-ink-2">{{ item.error }}</span>
			</li>
		</ul>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, Dialog, dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import QuarterScopeBar from "./QuarterScopeBar.vue"
import { can } from "@/data/permissions"
import { closeQuestionnaires, getQuestionnaires, type QuarterScope, type QuestionnaireRow } from "@/data/pmsReview"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const router = useRouter()
const scope = ref<QuarterScope>({ fiscalYear: "", quarter: "", company: "", department: "" })
const ready = computed(() => !!scope.value.fiscalYear && !!scope.value.quarter)

const rows = ref<QuestionnaireRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref("")
const status = ref("")
const selected = ref<string[]>([])
const closing = ref(false)
const failed = ref<{ questionnaire: string; error: string }[]>([])
let requestId = 0

async function load() {
	if (!ready.value) return
	const id = ++requestId
	loading.value = true
	error.value = null
	try {
		const data = await getQuestionnaires(scope.value)
		if (id === requestId) rows.value = data
	} catch (e: any) {
		if (id === requestId) error.value = e?.messages?.[0] || "Could not load the questionnaires"
	} finally {
		if (id === requestId) loading.value = false
	}
	selected.value = []
}
watch(scope, load, { deep: true })

const count = (value: string) => rows.value.filter((row) => row.status === value).length
const reviewsDone = computed(() => rows.value.reduce((sum, row) => sum + row.reviews_done, 0))
const reviewsTotal = computed(() => rows.value.reduce((sum, row) => sum + row.reviews_total, 0))
const nameOf = (questionnaire: string) => rows.value.find((row) => row.name === questionnaire)?.employee_name || questionnaire

const shown = computed(() => {
	const text = search.value.trim().toLowerCase()
	return rows.value.filter(
		(row) => (!status.value || row.status === status.value) && (!text || `${row.employee_name} ${row.employee}`.toLowerCase().includes(text))
	)
})
/** The open questionnaires to close: the selected ones, or every one shown. */
const closable = computed(() =>
	shown.value.filter((row) => row.status === "Open" && (!selected.value.length || selected.value.includes(row.name)))
)

function toggleStatus(value: string) {
	status.value = status.value === value ? "" : value
}
function clearFilters() {
	search.value = ""
	status.value = ""
}

function confirmClose() {
	dialog.confirm({
		title: "Close questionnaires",
		message: `Close ${closable.value.length} questionnaires? Each employee's line manager and peers are then asked for their review, and the questions can no longer be changed.`,
		confirmLabel: "Close and send",
		onConfirm: close,
	})
}

async function close() {
	closing.value = true
	try {
		const outcome = await closeQuestionnaires(closable.value.map((row) => row.name))
		failed.value = outcome.failed
		toast.success(`${outcome.closed.length} questionnaires closed`)
		await load()
	} finally {
		closing.value = false
	}
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)" },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "questions", label: "Questions", width: "100px", align: "right" },
	{ key: "status", label: "Status", width: "150px" },
	{
		key: "reviews_done",
		label: "Reviews in",
		width: "110px",
		align: "right",
		format: (_, row) => (row.reviews_total ? `${row.reviews_done} of ${row.reviews_total}` : "—"),
	},
]
</script>
