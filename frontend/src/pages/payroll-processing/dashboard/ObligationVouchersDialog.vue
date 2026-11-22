<template>
	<Dialog :open="!!obligation" :title="`${obligation?.obligation_name || ''}: vouchers and payment requests`" size="3xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="obligation" class="flex flex-col gap-4 text-[13px]">
			<section v-for="group in groups" :key="group.title" class="rounded-4 border border-ch-line">
				<h3 class="flex items-center justify-between border-b border-ch-line px-3 py-2 font-medium text-ch-ink">
					{{ group.title }}
					<span class="tabular-nums text-ch-ink-2">{{ formatCurrency(group.total) }}</span>
				</h3>
				<table v-if="group.vouchers.length" class="w-full text-left">
					<tbody>
						<tr v-for="voucher in group.vouchers" :key="voucher.voucher_no" class="border-t border-ch-line first:border-t-0">
							<td class="px-3 py-1.5">
								<a :href="voucherRoute(voucher)" target="_blank" class="font-medium text-ch-primary hover:underline">{{ voucher.voucher_no }}</a>
							</td>
							<td class="px-3 py-1.5 text-ch-ink-2">{{ voucher.voucher_type }}</td>
							<td class="px-3 py-1.5 text-ch-ink-2">{{ formatDateShort(voucher.date) }}</td>
							<td class="px-3 py-1.5 text-right tabular-nums">{{ formatCurrency(voucher.amount) }}</td>
						</tr>
					</tbody>
				</table>
				<p v-else class="px-3 py-3 text-ch-ink-3">{{ group.empty }}</p>
			</section>

			<section class="rounded-4 border border-ch-line">
				<h3 class="border-b border-ch-line px-3 py-2 font-medium text-ch-ink">Payment requests</h3>
				<div v-if="obligation.requests.length" class="flex flex-col gap-2 px-3 py-2">
					<PaymentRequestLine v-for="request in obligation.requests" :key="request.name" :request="request" @changed="$emit('changed')" />
				</div>
				<p v-else class="px-3 py-3 text-ch-ink-3">No payment was requested for this obligation yet</p>
			</section>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Dialog } from "frappe-ui"
import type { Obligation, Voucher } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort } from "@/utils/format"
import PaymentRequestLine from "../PaymentRequestLine.vue"

/** Every voucher that accrued or paid an obligation in the cycle, and the requests to pay it. */
const props = defineProps<{ obligation: Obligation | null }>()
defineEmits<{ close: []; changed: [] }>()

const groups = computed(() => [
	{ title: "Accrual vouchers", vouchers: props.obligation!.accruals, total: props.obligation!.payable, empty: "Nothing was accrued in this cycle" },
	{ title: "Payment vouchers", vouchers: props.obligation!.payments, total: props.obligation!.remitted, empty: "Nothing was paid in this cycle" },
])

/** Desk opens a voucher by the slug of its DocType. */
const voucherRoute = (voucher: Voucher) => `/desk/${voucher.voucher_type.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(voucher.voucher_no)}`
</script>
