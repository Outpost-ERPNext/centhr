<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<div class="flex flex-wrap items-center gap-2 text-[13px] text-ch-ink-3">
			<span>Audit for <b class="text-ch-ink">{{ cycleLabel(scope.from, scope.to) }}</b> · {{ scope.company || "All companies" }}</span>
			<Button class="ml-auto" icon-left="lucide-rotate-ccw" label="Re-run audit" :loading="loading" @click="reload" />
		</div>
		<div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
			<StatCard
				v-for="card in data?.cards || []"
				:key="card.key"
				clickable
				:active="check === card.key"
				:label="card.label"
				:value="card.info ? `${card.count} Active` : card.count ? `${card.count} Issues` : 'Passed'"
				:tone="card.info ? 'blue' : card.count ? 'amber' : 'green'"
				:loading="loading"
				@click="check = check === card.key ? 'status' : card.key"
			/>
		</div>
		<div class="flex flex-wrap items-center gap-2">
			<h3 class="text-[14px] font-medium text-ch-ink">{{ cardLabel }} — Details</h3>
			<SegmentedTabs v-model="view" :tabs="VIEWS.map((v) => ({ label: v.label, value: v.key, count: viewCounts[v.key] }))" />
		</div>
	</div>

	<FilterBar v-model:search="search" :total="filtered.length" :active="hasFilters" search-placeholder="Search name or ID" noun="employee" @clear="clear">
		<FilterLink v-model="department" doctype="Department" placeholder="Department" :filters="companyFilter" />
		<FilterLink v-model="structure" doctype="Salary Structure" placeholder="Salary structure" :filters="companyFilter" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="pageRows"
		:loading="loading"
		:error="error"
		:show-clear="hasFilters"
		empty-icon="lucide-shield-check"
		:empty-message="check === 'status' ? 'No employees match these filters' : 'No employee fails this check'"
		mobile-aside="payroll"
		min-width="1080px"
		@row-click="(row) => router.push(routeFor('Employee', row.name)!)"
		@clear-filters="clear"
	>
		<template #cell-name="{ row }">
			<span class="font-medium text-ch-primary">{{ row.name }}</span>
		</template>
		<template #cell-salary_structure="{ row }">
			<span v-if="row.salary_structure" class="truncate rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] font-medium text-ch-ink-2">{{ row.salary_structure }}</span>
			<StatusBadge v-else tone="amber" status="Missing" />
		</template>
		<template #cell-issues="{ row }">
			<div class="flex min-w-0 flex-wrap gap-1">
				<span
					v-for="(detail, key) in row.issues"
					:key="key"
					:title="detail"
					class="rounded-full bg-ch-amber-bg px-2 py-0.5 text-[11.5px] font-medium text-ch-amber-ink"
				>
					{{ ISSUE_LABELS[key] || key }}
				</span>
				<StatusBadge v-if="!Object.keys(row.issues).length" pill tone="green" status="Clear" />
			</div>
		</template>
		<template #cell-payroll="{ row }">
			<StatusBadge pill :tone="payrollTone(row)" :status="payrollStatus(row)" />
		</template>
		<template #cell-actions="{ row }">
			<div class="flex justify-end" @click.stop>
				<Button v-if="row.hold" size="sm" icon-left="lucide-play" label="Release" :loading="acting === row.name" @click="release(row)" />
				<Button v-else-if="row.status === 'Active'" size="sm" theme="red" icon-left="lucide-ban" label="Set hold" :loading="acting === row.name" @click="hold(row)" />
			</div>
		</template>
	</DataTable>
	<Pager v-model:page="page" v-model:page-size="pageSize" :total="filtered.length" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button, dialog, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import Pager from "@/components/Pager.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import { getAudit, releaseHold, setHold, useTabData, type AuditRow, type Scope } from "@/data/payrollDashboard"
import type { Tone } from "@/utils/status"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ scope: Scope }>()
const router = useRouter()
const { data, loading, error, reload } = useTabData(props.scope, getAudit)

const ISSUE_LABELS: Record<string, string> = {
	structure: "Structure",
	joiners: "New joiner",
	leave: "Pending leave",
	attendance: "Attendance",
	negative: "Negative pay",
	dimensions: "Cost center",
	bank: "Bank details",
}
const VIEWS = [
	{ key: "all", label: "All employees", test: () => true },
	{ key: "ready", label: "Ready to process", test: (r: AuditRow) => !r.hold && !Object.keys(r.issues).length },
	{ key: "hold", label: "On hold", test: (r: AuditRow) => !!r.hold },
	{ key: "action", label: "Action needed", test: (r: AuditRow) => !!Object.keys(r.issues).length },
]

const check = ref("status")
const view = ref("all")
const search = ref("")
const department = ref("")
const structure = ref("")
const page = ref(1)
const pageSize = ref(20)
const acting = ref<string | null>(null)

const cardLabel = computed(() => data.value?.cards.find((c) => c.key === check.value)?.label || "Employee Status")
const companyFilter = computed(() => (props.scope.company ? { company: props.scope.company } : undefined))
// The selected card narrows to employees failing that check; the chips count within it
const checked = computed(() => (data.value?.rows || []).filter((r) => check.value === "status" || check.value in r.issues))
const viewCounts = computed(() => Object.fromEntries(VIEWS.map((v) => [v.key, checked.value.filter(v.test).length])))
const filtered = computed(() => {
	const term = search.value.trim().toLowerCase()
	const test = VIEWS.find((v) => v.key === view.value)!.test
	return checked.value
		.filter(test)
		.filter((r) => !term || r.name.toLowerCase().includes(term) || r.employee_name.toLowerCase().includes(term))
		.filter((r) => !department.value || r.department === department.value)
		.filter((r) => !structure.value || r.salary_structure === structure.value)
})
const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
const hasFilters = computed(() => !!(search.value || department.value || structure.value || view.value !== "all"))
watch([check, view, search, department, structure, pageSize], () => (page.value = 1))

function clear() {
	search.value = department.value = structure.value = ""
	view.value = "all"
}

function payrollStatus(row: AuditRow) {
	if (row.hold) return "On Hold"
	if (row.slip_status) return row.slip_status
	return row.assignment ? "Eligible" : "Not eligible"
}

function payrollTone(row: AuditRow): Tone {
	if (row.hold) return "red"
	if (row.slip_status) return row.slip_status === "Submitted" ? "green" : "amber"
	return row.assignment ? "green" : "gray"
}

function hold(row: AuditRow) {
	dialog.confirm({
		title: "Hold salary",
		message: `Hold ${row.employee_name}'s salary for ${cycleLabel(props.scope.from, props.scope.to)}? Their salary slip is marked Withheld and left out of the bank entry until you release it.`,
		confirmLabel: "Set hold",
		theme: "red",
		onConfirm: () => act(row, () => setHold(row.name, props.scope), "Salary on hold"),
	})
}

function release(row: AuditRow) {
	return act(row, () => releaseHold(row.hold!), "Hold released")
}

async function act(row: AuditRow, call: () => Promise<unknown>, message: string) {
	acting.value = row.name
	try {
		await call()
		toast.success(message)
		await reload()
	} finally {
		acting.value = null
	}
}

const columns: Column[] = [
	{ key: "name", label: "Employee ID", width: "110px" },
	{ key: "employee_name", label: "Employee name", width: "minmax(170px,1.6fr)", class: "font-medium" },
	{ key: "department", label: "Department", width: "minmax(120px,1.1fr)", hideOnMobile: true },
	{ key: "salary_structure", label: "Salary structure", width: "minmax(150px,1.3fr)" },
	{ key: "issues", label: "Audit status", width: "minmax(170px,1.6fr)" },
	{ key: "payroll", label: "Payroll status", width: "110px" },
	{ key: "actions", label: "", width: "110px", align: "right" },
]
</script>
