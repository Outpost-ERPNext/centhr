<template>
	<Dialog :open="!!obligation" :title="`${obligation?.obligation_name || ''}: employee breakdown`" size="4xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="breakdown" class="flex flex-col gap-3 text-[13px]">
			<div class="grid grid-cols-3 gap-2">
				<StatCard label="From salary slips" :value="money(breakdown.total)" />
				<StatCard label="Booked without a slip" :value="money(breakdown.difference)" :tone="breakdown.difference ? 'amber' : undefined" />
				<StatCard label="Payable in the cycle" :value="money(breakdown.payable)" />
			</div>
			<div class="flex flex-wrap items-center gap-2">
				<p class="mr-auto text-ch-ink-3">
					<template v-if="breakdown.components.length">Salary components booked to the liability account: {{ breakdown.components.join(", ") }}.</template>
					<template v-else>No salary component is booked to this obligation's liability account, so nothing comes from salary slips.</template>
				</p>
				<Button icon-left="lucide-file-spreadsheet" label="Export (Excel)" :disabled="!breakdown.rows.length" :loading="exporting" @click="exportRows" />
			</div>
			<div class="max-h-[50vh] overflow-auto rounded-4 border border-ch-line">
				<table class="w-full min-w-[640px] text-left">
					<thead class="sticky top-0 z-[1] bg-ch-subtle text-ch-ink-3">
						<tr>
							<th class="px-3 py-2 font-normal">Employee</th>
							<th class="px-3 py-2 font-normal">Salary slip</th>
							<th v-for="component in breakdown.components" :key="component" class="px-3 py-2 text-right font-normal">{{ component }}</th>
							<th class="px-3 py-2 text-right font-normal">Total</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in breakdown.rows" :key="row.salary_slip" class="border-t border-ch-line">
							<td class="px-3 py-1.5">
								<div class="font-medium text-ch-ink">{{ row.employee_name }}</div>
								<div class="text-[12px] text-ch-ink-3">{{ [row.employee, row.department].filter(Boolean).join(" · ") }}</div>
							</td>
							<td class="px-3 py-1.5">
								<RouterLink :to="routeFor('Salary Slip', row.salary_slip)!" class="text-ch-primary hover:underline">{{ row.salary_slip }}</RouterLink>
							</td>
							<td v-for="component in breakdown.components" :key="component" class="px-3 py-1.5 text-right tabular-nums">{{ money(row.components[component] || 0) }}</td>
							<td class="px-3 py-1.5 text-right font-medium tabular-nums">{{ money(row.amount) }}</td>
						</tr>
						<tr v-if="!breakdown.rows.length">
							<td :colspan="breakdown.components.length + 3" class="px-3 py-6 text-center text-ch-ink-3">No submitted salary slip of this cycle carries these components</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
		<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Button, Dialog, LoadingIndicator } from "frappe-ui"
import StatCard from "@/components/StatCard.vue"
import { exportObligationBreakdown, getObligationBreakdown, type Obligation, type ObligationBreakdown, type Scope } from "@/data/payrollDashboard"
import { formatCurrency } from "@/utils/format"
import { routeFor } from "@/utils/routes"

/** Who an obligation's liability of the cycle comes from, by the salary components booked to its account. */
const props = defineProps<{ scope: Scope; obligation: Obligation | null }>()
defineEmits<{ close: [] }>()

const breakdown = ref<ObligationBreakdown | null>(null)
const exporting = ref(false)
watch(
	() => props.obligation,
	async (obligation) => {
		breakdown.value = null
		if (obligation) breakdown.value = await getObligationBreakdown(obligation.name, props.scope)
	},
	{ immediate: true }
)

const money = (value: number) => formatCurrency(value, breakdown.value?.rows[0]?.currency)

async function exportRows() {
	exporting.value = true
	try {
		await exportObligationBreakdown(props.obligation!.name, props.scope)
	} catch {
		// downloadFile already showed the server's message
	} finally {
		exporting.value = false
	}
}
</script>
