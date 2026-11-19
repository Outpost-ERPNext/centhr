<template>
	<div class="flex flex-col gap-3">
		<div class="flex flex-wrap items-center gap-2">
			<SegmentedTabs v-model="filter" :tabs="tabs" />
			<div class="relative ml-auto w-full sm:w-56">
				<span class="lucide-search pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-ch-ink-3" />
				<input
					v-model="search"
					type="search"
					placeholder="Search employee, ID, department"
					aria-label="Search employee, ID, department"
					class="h-7 w-full rounded-3 border-0 bg-ch-subtle pl-7 pr-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4 focus:ring-2 focus:ring-[var(--ch-line-2)]"
				/>
			</div>
			<Dropdown :options="downloads" align="end">
				<Button icon-left="lucide-download" icon-right="lucide-chevron-down" label="Download" :loading="downloading" />
			</Dropdown>
		</div>

		<div class="max-h-[46vh] overflow-auto rounded-4 border border-ch-line">
			<table class="w-full min-w-[1040px] text-left">
				<thead class="sticky top-0 z-[1] bg-ch-subtle text-ch-ink-3">
					<tr>
						<th class="w-8 px-2 py-2" />
						<th class="px-3 py-2 font-normal">Employee ID</th>
						<th class="px-3 py-2 font-normal">Employee name</th>
						<th class="px-3 py-2 font-normal">Department</th>
						<th class="px-3 py-2 text-right font-normal">ERP net pay</th>
						<th class="px-3 py-2 text-right font-normal">Excel net pay</th>
						<th class="px-3 py-2 text-right font-normal">Variance</th>
						<th class="px-3 py-2 text-right font-normal">Paid days (ERP / Excel)</th>
						<th class="px-3 py-2 font-normal">Status</th>
						<th class="px-3 py-2 font-normal">Differences &amp; remarks</th>
					</tr>
				</thead>
				<tbody>
					<template v-for="row in shown" :key="row.employee">
						<tr
							class="border-t border-ch-line"
							:class="[row.components.length ? 'cursor-pointer hover:bg-ch-hover' : '', row.status === 'Discrepancy' ? 'bg-ch-red-bg/40' : '']"
							@click="row.components.length && toggle(row.employee)"
						>
							<td class="px-2 py-1.5">
								<button
									v-if="row.components.length"
									type="button"
									class="flex size-5 items-center justify-center rounded-2 text-ch-ink-3 hover:text-ch-ink"
									:aria-expanded="expanded === row.employee"
									:aria-label="`Salary components of ${row.employee_name || row.employee}`"
									@click.stop="toggle(row.employee)"
								>
									<span class="lucide-chevron-right size-4 transition-transform" :class="{ 'rotate-90': expanded === row.employee }" />
								</button>
							</td>
							<td class="px-3 py-1.5 font-medium tabular-nums text-ch-ink">{{ row.employee }}</td>
							<td class="px-3 py-1.5 text-ch-ink">{{ row.employee_name || "—" }}</td>
							<td class="px-3 py-1.5 text-ch-ink-2">{{ row.department || "—" }}</td>
							<td class="px-3 py-1.5 text-right tabular-nums">{{ money(row.erp_net_pay, row) }}</td>
							<td class="px-3 py-1.5 text-right tabular-nums">{{ money(row.excel_net_pay, row) }}</td>
							<td class="px-3 py-1.5 text-right tabular-nums" :class="row.variance ? 'font-medium text-ch-red-ink' : 'text-ch-ink-3'">{{ money(row.variance, row) }}</td>
							<td class="px-3 py-1.5 text-right tabular-nums text-ch-ink-2">{{ days(row.erp_payment_days) }} / {{ days(row.excel_payment_days) }}</td>
							<td class="px-3 py-1.5"><StatusBadge pill :tone="RECONCILE_TONES[row.status]" :status="row.status" /></td>
							<td class="px-3 py-1.5 text-ch-ink-2">
								<div v-for="remark in row.remarks" :key="remark">{{ remark }}</div>
							</td>
						</tr>
						<tr v-if="expanded === row.employee" class="border-t border-ch-line bg-ch-subtle">
							<td />
							<td colspan="9" class="px-3 py-3">
								<ReconcileComponents :row="row" />
							</td>
						</tr>
					</template>
					<tr v-if="!shown.length">
						<td colspan="10" class="px-3 py-6 text-center text-ch-ink-3">Nothing in this group</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dropdown } from "frappe-ui"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { RECONCILE_STATUSES, RECONCILE_TONES, exportReconciliation, type Reconciliation, type ReconcileRow, type ReconcileStatus } from "@/data/masterSheet"
import type { Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatNumber } from "@/utils/format"
import ReconcileComponents from "./ReconcileComponents.vue"

/** The reconciled employees: by status, searchable, with each one's salary components a click away. */
const props = defineProps<{ scope: Scope; rows: ReconcileRow[]; summary: NonNullable<Reconciliation["summary"]> }>()

const LABELS: Record<ReconcileStatus, string> = {
	Discrepancy: "Discrepancies",
	Matched: "Matched",
	"Missing in ERP": "Missing in ERP",
	"Missing in Excel": "Missing in Excel",
}

const filter = ref("All")
const search = ref("")
// The employee whose salary components are shown
const expanded = ref<string | null>(null)
const downloading = ref(false)
watch(
	() => props.rows,
	() => (expanded.value = null)
)

const tabs = computed(() => [
	{ label: "All records", value: "All", count: props.rows.length },
	...RECONCILE_STATUSES.map((status) => ({ label: LABELS[status], value: status, count: props.summary[status] })),
])
const shown = computed(() => {
	const term = search.value.trim().toLowerCase()
	return props.rows
		.filter((row) => filter.value === "All" || row.status === filter.value)
		.filter((row) => !term || [row.employee, row.employee_name, row.department].some((text) => text?.toLowerCase().includes(term)))
})

/** One Excel file per group, so Finance gets only the rows it has to look at. */
const downloads = computed(() => [
	{ label: `All records (${props.rows.length})`, icon: "lucide-file-spreadsheet", onClick: () => download() },
	...RECONCILE_STATUSES.map((status) => ({
		label: `${LABELS[status]} (${props.summary[status]})`,
		icon: "lucide-file-spreadsheet",
		disabled: !props.summary[status],
		onClick: () => download(status),
	})),
])

async function download(status?: ReconcileStatus) {
	downloading.value = true
	try {
		await exportReconciliation(props.scope, status)
	} catch {
		// downloadFile already showed the server's message
	} finally {
		downloading.value = false
	}
}

const toggle = (employee: string) => (expanded.value = expanded.value === employee ? null : employee)
const money = (value: number | null, row: ReconcileRow) => (value === null || value === undefined ? "—" : formatCurrency(value, row.currency))
const days = (value: number | null) => (value === null || value === undefined ? "—" : formatNumber(value))
</script>
