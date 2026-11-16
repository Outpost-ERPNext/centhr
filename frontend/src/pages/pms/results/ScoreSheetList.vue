<template>
	<PageHeader :crumbs="[{ label: 'Score Sheets' }]">
		<template #actions>
			<template v-if="can('PMS Score Sheet').create">
				<Button
					icon-left="lucide-wand-sparkles"
					label="Generate"
					:tooltip="scope.company ? undefined : 'Choose a company to generate its score sheets'"
					:disabled="!scope.company || !ready"
					:loading="busy === 'generate'"
					@click="generate"
				/>
				<Button icon-left="lucide-x" label="Reject" :disabled="!pendingSelected.length" :loading="busy === 'reject'" @click="confirmDecide('reject')" />
				<Button
					variant="solid"
					icon-left="lucide-check"
					:label="pendingSelected.length ? `Approve ${pendingSelected.length}` : 'Approve'"
					:disabled="!pendingSelected.length"
					:loading="busy === 'approve'"
					@click="confirmDecide('approve')"
				/>
			</template>
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<QuarterScopeBar v-model="scope" />

		<p class="px-5 text-[13px] text-ch-ink-3">
			A score sheet records what an employee's overall score for the quarter leads to. Generate creates one for every employee who has an
			overall score. Open a sheet to normalize its score or set the effective date. Approving records the decision; it does not change payroll.
		</p>

		<FilterBar v-model:search="search" :total="shown.length" :active="!!search || !!status" search-placeholder="Search employees" noun="score sheet" @clear="clearFilters">
			<FilterSelect v-model="status" :options="['Pending', 'Approved', 'Rejected']" placeholder="Status" />
		</FilterBar>

		<DataTable
			v-model:selected="selected"
			:columns="columns"
			:rows="shown"
			:loading="loading"
			:error="error"
			:selectable="can('PMS Score Sheet').submit"
			:show-clear="!!search || !!status"
			empty-icon="lucide-receipt-text"
			:empty-message="rows.length ? 'No score sheets match these filters' : 'No score sheets for this quarter yet'"
			mobile-aside="status"
			@row-click="(row) => router.push(routeFor('PMS Score Sheet', row.name)!)"
			@clear-filters="clearFilters"
		>
			<template #cell-employee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.department].filter(Boolean).join(" · ") }}</div>
				</div>
			</template>
			<template #cell-outcome="{ row }">
				<StatusBadge v-if="row.outcome" :tone="OUTCOME_TONES[row.outcome]" :status="row.outcome === 'Increment' ? `Increment ${formatNumber(row.increment)}%` : row.outcome" />
				<span v-else class="text-ch-ink-3">No band</span>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge :tone="STATUS_TONES[row.status]" :status="row.status" />
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import QuarterScopeBar from "../review/QuarterScopeBar.vue"
import { getList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { decideScoreSheets, generateScoreSheets, type QuarterScope } from "@/data/pmsReview"
import { formatCurrency, formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import type { Tone } from "@/utils/status"

const OUTCOME_TONES: Record<string, Tone> = { Increment: "green", PIP: "amber", Fire: "red" }
const STATUS_TONES: Record<string, Tone> = { Pending: "amber", Approved: "green", Rejected: "red" }
const FIELDS = ["name", "employee", "employee_name", "department", "calculated_score", "check_normalized_score", "normalized_score", "outcome", "increment", "old_ctc", "new_ctc", "currency", "status", "docstatus"]

const router = useRouter()
const scope = ref<QuarterScope>({ fiscalYear: "", quarter: "", company: "", department: "" })
const ready = computed(() => !!scope.value.fiscalYear && !!scope.value.quarter)

const rows = ref<Record<string, any>[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const search = ref("")
const status = ref("")
const selected = ref<string[]>([])
const busy = ref<"generate" | "approve" | "reject" | null>(null)
let requestId = 0

async function load() {
	if (!ready.value) return
	const id = ++requestId
	loading.value = true
	error.value = null
	const filters: Filter[] = [
		["fiscal_year", "=", scope.value.fiscalYear],
		["quarter", "=", scope.value.quarter],
		["docstatus", "!=", 2],
	]
	if (scope.value.company) filters.push(["company", "=", scope.value.company])
	if (scope.value.department) filters.push(["department", "=", scope.value.department])
	try {
		const data = await getList({ doctype: "PMS Score Sheet", fields: FIELDS, filters, order_by: "employee_name asc", limit: 0 })
		if (id === requestId) rows.value = data
	} catch (e: any) {
		if (id === requestId) error.value = e?.messages?.[0] || "Could not load the score sheets"
	} finally {
		if (id === requestId) loading.value = false
	}
	selected.value = []
}
watch(scope, load, { deep: true })

const shown = computed(() => {
	const text = search.value.trim().toLowerCase()
	return rows.value.filter(
		(row) => (!status.value || row.status === status.value) && (!text || `${row.employee_name} ${row.employee}`.toLowerCase().includes(text))
	)
})
/** Only sheets that are not approved yet can be approved or rejected. */
const pendingSelected = computed(() => rows.value.filter((row) => selected.value.includes(row.name) && row.docstatus === 0))

function clearFilters() {
	search.value = ""
	status.value = ""
}

async function generate() {
	busy.value = "generate"
	try {
		const outcome = await generateScoreSheets(scope.value)
		toast.success(
			`${outcome.created.length} score sheets created, ${outcome.existing} existed already, ${outcome.not_ready} employees have no overall score yet`
		)
		await load()
	} finally {
		busy.value = null
	}
}

function confirmDecide(decision: "approve" | "reject") {
	const count = pendingSelected.value.length
	dialog.confirm({
		title: decision === "approve" ? "Approve score sheets" : "Reject score sheets",
		message:
			decision === "approve"
				? `Approve ${count} score sheets? An approved sheet can no longer be edited.`
				: `Reject ${count} score sheets? They stay as drafts marked Rejected.`,
		confirmLabel: decision === "approve" ? "Approve" : "Reject",
		theme: decision === "reject" ? "red" : undefined,
		onConfirm: () => decide(decision),
	})
}

async function decide(decision: "approve" | "reject") {
	busy.value = decision
	try {
		const count = await decideScoreSheets(pendingSelected.value.map((row) => row.name), decision)
		toast.success(`${count} score sheets ${decision === "approve" ? "approved" : "rejected"}`)
		await load()
	} finally {
		busy.value = null
	}
}

const money = (value: number, row: Record<string, any>) => (value ? formatCurrency(value, row.currency) : "—")

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,2fr)" },
	{
		key: "calculated_score",
		label: "Score",
		width: "110px",
		align: "right",
		format: (v, row) => (row.check_normalized_score ? `${formatNumber(row.normalized_score, 2)} (norm.)` : formatNumber(v, 2)),
	},
	{ key: "outcome", label: "Outcome", width: "150px" },
	{ key: "old_ctc", label: "Old CTC", width: "130px", align: "right", hideOnMobile: true, format: money },
	{ key: "new_ctc", label: "New CTC", width: "130px", align: "right", hideOnMobile: true, format: money },
	{ key: "status", label: "Status", width: "110px" },
]
</script>
