<template>
	<Dialog :open="!!name" :title="slip ? slip.employee_name : 'Salary slip'" size="2xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="slip" class="flex flex-col gap-4 text-[13px]">
			<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-ch-ink-3">
				<span class="tabular-nums">{{ slip.name }}</span>
				<StatusBadge pill doctype="Salary Slip" :status="slip.status" />
				<span>{{ [slip.employee, slip.designation, slip.department].filter(Boolean).join(" · ") }}</span>
				<span class="ml-auto">{{ formatDateShort(slip.start_date) }} → {{ formatDateShort(slip.end_date) }}</span>
			</div>

			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
				<div v-for="item in days" :key="item.label" class="rounded-4 border border-ch-line px-3 py-2">
					<div class="text-[11.5px] uppercase tracking-wide text-ch-ink-3">{{ item.label }}</div>
					<div class="text-[16px] font-semibold tabular-nums" :class="item.warn ? 'text-ch-amber-ink' : 'text-ch-ink'">{{ formatNumber(item.value) }}</div>
				</div>
			</div>

			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<section v-for="part in parts" :key="part.title" class="rounded-4 border border-ch-line">
					<h3 class="border-b border-ch-line px-3 py-2 font-medium text-ch-ink">{{ part.title }}</h3>
					<dl class="px-3 py-1">
						<div v-for="line in part.lines" :key="line.salary_component" class="flex justify-between gap-3 py-1">
							<dt class="truncate text-ch-ink-2">{{ line.salary_component }}</dt>
							<dd class="tabular-nums text-ch-ink">{{ money(line.amount) }}</dd>
						</div>
						<p v-if="!part.lines.length" class="py-2 text-ch-ink-3">None</p>
					</dl>
					<div class="flex justify-between border-t border-ch-line px-3 py-2 font-medium text-ch-ink">
						<span>{{ part.totalLabel }}</span>
						<span class="tabular-nums">{{ money(part.total) }}</span>
					</div>
				</section>
			</div>

			<div class="flex items-center justify-between rounded-4 px-4 py-3" :class="slip.net_pay > 0 ? 'bg-ch-green-bg text-ch-green-ink' : 'bg-ch-red-bg text-ch-red-ink'">
				<span class="font-medium">Net pay</span>
				<span class="text-[18px] font-semibold tabular-nums">{{ money(slip.net_pay) }}</span>
			</div>

			<p v-if="slip.bank_name || slip.bank_account_no" class="text-ch-ink-3">
				Paid to {{ [slip.bank_name, slip.bank_account_no].filter(Boolean).join(" · ") }}
			</p>
		</div>
		<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>

		<template #actions>
			<div class="flex flex-wrap justify-end gap-2">
				<template v-if="slip?.docstatus === 0">
					<Button theme="red" icon-left="lucide-trash-2" label="Delete" @click="$emit('action', 'delete', slip.name)" />
					<Button icon-left="lucide-refresh-cw" label="Recalculate" @click="$emit('action', 'recalculate', slip.name)" />
				</template>
				<Button v-if="slip" variant="solid" icon-left="lucide-external-link" label="Open full slip" :route="routeFor('Salary Slip', slip.name)!" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, LoadingIndicator } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { getSlipDetails, type SlipDetails } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort, formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

/** A salary slip at a glance, without leaving the dashboard: days, earnings, deductions and net pay. */
const props = defineProps<{ name: string | null }>()
defineEmits<{ close: []; action: [action: "recalculate" | "delete", name: string] }>()

const slip = ref<SlipDetails | null>(null)
watch(
	() => props.name,
	async (name) => {
		slip.value = null
		if (name) slip.value = await getSlipDetails(name)
	},
	{ immediate: true }
)

const money = (value: number) => formatCurrency(value, slip.value?.currency)
const days = computed(() => [
	{ label: "Working days", value: slip.value!.total_working_days },
	{ label: "Payment days", value: slip.value!.payment_days },
	{ label: "Absent", value: slip.value!.absent_days, warn: slip.value!.absent_days > 0 },
	{ label: "Leave without pay", value: slip.value!.leave_without_pay, warn: slip.value!.leave_without_pay > 0 },
])
const parts = computed(() => [
	{ title: "Earnings", lines: slip.value!.earnings, totalLabel: "Gross pay", total: slip.value!.gross_pay },
	{ title: "Deductions", lines: slip.value!.deductions, totalLabel: "Total deductions", total: slip.value!.total_deduction },
])
</script>
