<template>
	<Dialog v-model:open="open" title="Reconcile with the master Excel sheet" size="4xl">
		<div class="flex flex-col gap-4 text-[13px]">
			<p class="text-ch-ink-3">
				Upload Finance's payroll sheet for {{ cycleLabel(scope.from, scope.to) }} to compare it with the salary slips here. The first row
				names the columns: Employee ID and Net Pay are needed; Payment Days, Gross Pay and Total Deduction are compared when present.
				Rows without a net pay are skipped. Nothing is saved or changed.
			</p>
			<div class="flex flex-wrap items-center gap-2">
				<input ref="input" type="file" accept=".xlsx,.csv" class="hidden" @change="pick" />
				<Button variant="solid" icon-left="lucide-upload" :label="result ? 'Upload another sheet' : 'Upload sheet'" :loading="busy" @click="input?.click()" />
				<Button icon-left="lucide-download" label="Download template" @click="downloadMasterTemplate(scope)" />
				<span v-if="fileName" class="truncate text-ch-ink-3">{{ fileName }}</span>
			</div>
			<p v-if="error" class="rounded-4 bg-ch-red-bg px-3 py-2 text-ch-red-ink" role="alert">{{ error }}</p>

			<template v-if="result">
				<p v-if="result.ignored" class="rounded-4 bg-ch-subtle px-3 py-2 text-ch-ink-2">
					{{ result.ignored }} rows of the sheet have no net pay and were not compared.
				</p>
				<SegmentedTabs v-model="filter" :tabs="tabs" />
				<div class="max-h-[46vh] overflow-auto rounded-4 border border-ch-line">
					<table class="w-full min-w-[720px] text-left">
						<thead class="sticky top-0 bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-2 font-normal">Employee</th>
								<th class="px-3 py-2 text-right font-normal">Net pay here</th>
								<th class="px-3 py-2 text-right font-normal">Net pay in Excel</th>
								<th class="px-3 py-2 text-right font-normal">Difference</th>
								<th class="px-3 py-2 text-right font-normal">Pay days here / Excel</th>
								<th class="px-3 py-2 font-normal">Result</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in shown" :key="row.employee" class="border-t border-ch-line">
								<td class="px-3 py-1.5">
									<div class="font-medium text-ch-ink">{{ row.employee_name || row.employee }}</div>
									<div v-if="row.employee_name" class="text-[12px] text-ch-ink-3">{{ row.employee }}</div>
								</td>
								<td class="px-3 py-1.5 text-right tabular-nums">{{ money(row.erp_net_pay, row) }}</td>
								<td class="px-3 py-1.5 text-right tabular-nums">{{ money(row.excel_net_pay, row) }}</td>
								<td class="px-3 py-1.5 text-right tabular-nums" :class="row.variance ? 'font-medium text-ch-red-ink' : 'text-ch-ink-3'">{{ money(row.variance, row) }}</td>
								<td class="px-3 py-1.5 text-right tabular-nums text-ch-ink-2">{{ days(row.erp_payment_days) }} / {{ days(row.excel_payment_days) }}</td>
								<td class="px-3 py-1.5"><StatusBadge pill :tone="RECONCILE_TONES[row.status]" :status="row.status" /></td>
							</tr>
							<tr v-if="!shown.length">
								<td colspan="6" class="px-3 py-6 text-center text-ch-ink-3">Nothing in this group</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog } from "frappe-ui"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import { downloadMasterTemplate, reconcileMasterSheet, type ReconcileResult, type ReconcileRow, type ReconcileStatus, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"

const RECONCILE_TONES: Record<ReconcileStatus, Tone> = { Matched: "green", Discrepancy: "red", "Missing in Excel": "amber", "Missing in ERP": "amber" }
const STATUSES: ReconcileStatus[] = ["Discrepancy", "Missing in Excel", "Missing in ERP", "Matched"]

/** Finance's master payroll sheet against the cycle's salary slips. The result also marks the slips in the grid. */
const props = defineProps<{ scope: Scope }>()
const emit = defineEmits<{ result: [result: ReconcileResult] }>()
const open = defineModel<boolean>("open", { default: false })

const input = ref<HTMLInputElement | null>(null)
const result = ref<ReconcileResult | null>(null)
const fileName = ref("")
const filter = ref("All")
const busy = ref(false)
const error = ref("")

async function pick(event: Event) {
	const target = event.target as HTMLInputElement
	const file = target.files?.[0]
	// Picking the same file again must fire the change event too
	target.value = ""
	if (!file) return
	busy.value = true
	error.value = ""
	try {
		result.value = await reconcileMasterSheet(props.scope, file)
		fileName.value = file.name
		filter.value = "All"
		emit("result", result.value)
	} catch (e: any) {
		error.value = e?.message || "Could not read the sheet"
	} finally {
		busy.value = false
	}
}

const tabs = computed(() => [
	{ label: "All", value: "All", count: result.value?.rows.length || 0 },
	...STATUSES.map((status) => ({ label: status, value: status, count: result.value?.summary[status] || 0 })),
])
const shown = computed(() => (result.value?.rows || []).filter((row) => filter.value === "All" || row.status === filter.value))

const money = (value: number | null, row: ReconcileRow) => (value === null || value === undefined ? "—" : formatCurrency(value, row.currency))
const days = (value: number | null) => (value === null || value === undefined ? "—" : formatNumber(value))
</script>
