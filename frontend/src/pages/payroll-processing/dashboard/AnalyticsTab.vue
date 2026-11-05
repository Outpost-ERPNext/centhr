<template>
	<div class="flex flex-col gap-3 px-5 pt-3">
		<SegmentedTabs v-model="view" :tabs="VIEWS" />

		<template v-if="view === 'journal' && data?.summary">
			<div class="grid grid-cols-2 gap-2 lg:grid-cols-4">
				<StatCard label="Reconciled employees" :value="`${data.summary.reconciled}`" :sub="journalNote" />
				<StatCard label="Salary earnings" :value="money(data.summary.salary_earnings)" />
				<StatCard label="Journal expense (GL)" :value="money(data.summary.journal_expense)" tone="blue" />
				<StatCard label="Earnings variance" :value="money(data.summary.earnings_variance)" :tone="data.summary.earnings_variance ? 'red' : 'green'" />
				<StatCard label="Salary deductions" :value="money(data.summary.salary_deductions)" />
				<StatCard label="Journal provisions (GL)" :value="money(data.summary.journal_provisions)" tone="amber" />
				<StatCard label="Deductions variance" :value="money(data.summary.deductions_variance)" :tone="data.summary.deductions_variance ? 'red' : 'green'" />
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<SegmentedTabs v-model="journalFilter" :tabs="JOURNAL_FILTERS.map((f) => ({ label: f, value: f, count: journalCounts[f] }))" />
				<a
					v-for="je in data.journal_entries"
					:key="je"
					:href="`/desk/journal-entry/${encodeURIComponent(je)}`"
					target="_blank"
					class="text-[12.5px] text-ch-ink-2 underline-offset-2 hover:underline"
				>
					{{ je }} ↗
				</a>
			</div>
		</template>
		<p v-else-if="view === 'months'" class="text-[12.5px] text-ch-ink-3">The selected cycle and the five before it.</p>
	</div>

	<div class="pt-3">
		<DataTable
			:columns="columns"
			:rows="rows"
			row-key="key"
			:clickable="view === 'employee' || view === 'journal'"
			:loading="loading"
			:error="error"
			empty-icon="lucide-chart-column"
			empty-message="No salary slips in this cycle"
			min-width="900px"
			@row-click="(row) => router.push(routeFor('Salary Slip', row.name)!)"
		>
			<template #cell-share="{ row }">
				<div class="flex items-center gap-2">
					<div class="h-1.5 flex-1 overflow-hidden rounded-full bg-ch-subtle">
						<div class="h-full rounded-full bg-ch-primary" :style="{ width: `${Math.min(100, row.share)}%` }" />
					</div>
					<span class="w-12 text-right tabular-nums text-ch-ink-3">{{ row.share.toFixed(1) }}%</span>
				</div>
			</template>
			<template #cell-type="{ row }">
				<StatusBadge :tone="row.type === 'Earning' ? 'green' : 'red'" :status="row.type" />
			</template>
			<template #cell-journal_status="{ row }">
				<StatusBadge pill :tone="JOURNAL_TONES[row.journal_status]" :status="row.journal_status" />
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import DataTable, { type Column } from "@/components/DataTable.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import { getAnalytics, useTabData, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ scope: Scope }>()
const router = useRouter()

const VIEWS = [
	{ label: "By department", value: "department" },
	{ label: "By salary component", value: "component" },
	{ label: "By employee", value: "employee" },
	{ label: "Multi-month comparison", value: "months" },
	{ label: "Payroll journal summary", value: "journal" },
]
const JOURNAL_FILTERS = ["All", "Confirmed", "Discrepancy", "Booked in total", "Not booked"]
const JOURNAL_TONES: Record<string, Tone> = { Confirmed: "green", Discrepancy: "red", "Booked in total": "blue", "Not booked": "amber" }

const view = ref("department")
const journalFilter = ref("All")
const { data, loading, error, reload } = useTabData(props.scope, (scope) => getAnalytics(view.value, scope))
watch(view, () => {
	data.value = null
	reload()
})

const money = (v: number) => formatCurrency(v)
const journalNote = computed(() => (data.value?.journal_entries?.length ? `${data.value.journal_entries.length} journal entries` : "No accrual booked yet"))
const journalCounts = computed(() =>
	Object.fromEntries(JOURNAL_FILTERS.map((f) => [f, (data.value?.rows || []).filter((r: any) => f === "All" || r.journal_status === f).length]))
)

const rows = computed(() => {
	const list = (data.value?.rows || []).filter((r: any) => view.value !== "journal" || journalFilter.value === "All" || r.journal_status === journalFilter.value)
	const total = list.reduce((sum: number, r: any) => sum + (r.net_pay ?? r.amount ?? 0), 0) || 1
	return list.map((r: any, index: number) => ({
		...r,
		key: r.name || r.department || (r.salary_component && `${r.salary_component}-${r.type}`) || r.from_date || index,
		share: r.share ?? ((r.net_pay ?? r.amount ?? 0) / total) * 100,
		period: r.from_date ? cycleLabel(r.from_date, r.to_date) : undefined,
		average: r.headcount ? r.net_pay / r.headcount : undefined,
	}))
})

const amount = (label: string, key: string): Column => ({ key, label, width: "minmax(120px,1fr)", align: "right", format: (v, r) => formatCurrency(v, r.currency) })
const count = (label: string, key: string): Column => ({ key, label, width: "100px", align: "right", format: (v) => formatNumber(v) })
const share: Column = { key: "share", label: "Share of total", width: "minmax(160px,1.4fr)" }
const employee: Column = { key: "employee_name", label: "Employee", width: "minmax(200px,1.8fr)", class: "font-medium" }

const columns = computed<Column[]>(() => {
	switch (view.value) {
		case "department":
			return [{ key: "department", label: "Department", width: "minmax(180px,1.6fr)", class: "font-medium" }, count("Headcount", "headcount"), amount("Gross", "gross_pay"), amount("Deductions", "total_deduction"), amount("Net pay", "net_pay"), amount("Average net", "average"), share]
		case "component":
			return [{ key: "salary_component", label: "Salary component", width: "minmax(200px,1.8fr)", class: "font-medium" }, { key: "type", label: "Type", width: "110px" }, count("Employees", "employees"), amount("Amount", "amount"), share]
		case "employee":
			return [employee, { key: "department", label: "Department", width: "minmax(130px,1.2fr)" }, amount("Gross", "gross_pay"), amount("Deductions", "total_deduction"), amount("Net pay", "net_pay"), share]
		case "months":
			return [{ key: "period", label: "Pay cycle", width: "minmax(180px,1.6fr)", class: "font-medium" }, count("Headcount", "headcount"), amount("Gross", "gross_pay"), amount("Deductions", "total_deduction"), amount("Net pay", "net_pay"), share]
		default:
			return [employee, amount("Salary earnings", "gross_pay"), amount("Deductions", "total_deduction"), amount("Net pay", "net_pay"), amount("Journal net", "journal_net"), amount("Variance", "variance"), { key: "journal_status", label: "Journal status", width: "140px" }]
	}
})
</script>
