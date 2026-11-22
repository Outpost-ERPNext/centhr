<template>
	<Dialog :open="!!payrollEntry" :title="`Payout list of ${payrollEntry || ''}`" size="4xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="payouts" class="flex flex-col gap-3 text-[13px]">
			<div class="flex flex-wrap items-center gap-2">
				<span class="text-ch-ink-3">
					{{ formatNumber(payouts.rows.length) }} employees · <b class="tabular-nums text-ch-ink">{{ formatCurrency(payouts.total, currency) }}</b>
				</span>
				<StatusBadge v-if="payouts.missing_accounts" pill tone="red" :status="`${payouts.missing_accounts} without an account number`" />
				<Button class="ml-auto" icon-left="lucide-file-spreadsheet" label="Export (Excel)" :loading="exporting" @click="exportRows" />
			</div>
			<div class="max-h-[56vh] overflow-auto rounded-4 border border-ch-line">
				<table class="w-full min-w-[760px] text-left">
					<thead class="sticky top-0 z-[1] bg-ch-subtle text-ch-ink-3">
						<tr>
							<th class="px-3 py-2 font-normal">Employee</th>
							<th class="px-3 py-2 font-normal">Paid by</th>
							<th class="px-3 py-2 font-normal">Bank</th>
							<th class="px-3 py-2 font-normal">Account number</th>
							<th class="px-3 py-2 text-right font-normal">Net pay</th>
							<th class="px-3 py-2 font-normal">Slip</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in payouts.rows" :key="row.name" class="border-t border-ch-line" :class="row.missing_account ? 'bg-ch-red-bg/40' : ''">
							<td class="px-3 py-1.5">
								<div class="font-medium text-ch-ink">{{ row.employee_name }}</div>
								<div class="text-[12px] text-ch-ink-3">{{ [row.employee, row.department].filter(Boolean).join(" · ") }}</div>
							</td>
							<td class="px-3 py-1.5 text-ch-ink-2">{{ row.paid_by || "—" }}</td>
							<td class="px-3 py-1.5 text-ch-ink-2">{{ row.bank_name || "—" }}</td>
							<td class="px-3 py-1.5 tabular-nums" :class="row.missing_account ? 'font-medium text-ch-red-ink' : 'text-ch-ink'">
								{{ row.bank_account_no || (row.missing_account ? "Missing" : "—") }}
							</td>
							<td class="px-3 py-1.5 text-right font-medium tabular-nums">{{ formatCurrency(row.net_pay, row.currency) }}</td>
							<td class="px-3 py-1.5"><StatusBadge pill doctype="Salary Slip" :status="row.status" /></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>
		<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, LoadingIndicator } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { exportPayoutList, getPayoutList, type PayoutList } from "@/data/payrollDashboard"
import { formatCurrency, formatNumber } from "@/utils/format"

/** Who a payroll entry pays, with the bank details Finance needs. */
const props = defineProps<{ payrollEntry: string | null }>()
defineEmits<{ close: [] }>()

const payouts = ref<PayoutList | null>(null)
const exporting = ref(false)
watch(
	() => props.payrollEntry,
	async (name) => {
		payouts.value = null
		if (name) payouts.value = await getPayoutList(name)
	},
	{ immediate: true }
)
const currency = computed(() => payouts.value?.rows[0]?.currency)

async function exportRows() {
	exporting.value = true
	try {
		await exportPayoutList(props.payrollEntry!)
	} catch {
		// downloadFile already showed the server's message
	} finally {
		exporting.value = false
	}
}
</script>
