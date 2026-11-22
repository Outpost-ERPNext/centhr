<template>
	<div class="flex flex-col gap-3 px-5 py-3">
		<div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
			<StatCard label="Total accrued (payable)" :value="formatCurrency(total('payable'))" :loading="loading" />
			<StatCard label="Total remitted (paid)" :value="formatCurrency(total('remitted'))" tone="green" :loading="loading" />
			<StatCard label="Outstanding balance" :value="formatCurrency(total('balance'))" :tone="total('balance') > 0 ? 'red' : 'green'" :loading="loading" />
			<StatCard label="Deadline status" :value="overallStatus" :tone="STATUS_TONES[overallStatus]" :sub="`For ${cycleLabel(scope.from, scope.to)}`" :loading="loading" />
		</div>

		<section class="rounded-5 border border-ch-line bg-ch-surface">
			<header class="flex flex-wrap items-center gap-2 border-b border-ch-line px-4 py-2.5">
				<h3 class="text-[14px] font-medium text-ch-ink">Statutory obligations</h3>
				<span class="text-[12.5px] text-ch-ink-3">Credits and debits to each obligation's liability account in the cycle</span>
				<Button class="ml-auto" size="sm" icon-left="lucide-settings" label="Configure obligations" @click="configOpen = true" />
			</header>
			<p v-if="data?.no_access" class="px-4 py-6 text-center text-[13px] text-ch-ink-3">You need access to the general ledger to see statutory obligations.</p>
			<DataTable
				v-else
				:columns="columns"
				:rows="obligations"
				:loading="loading"
				:error="error"
				:clickable="false"
				empty-icon="lucide-shield"
				empty-message="No statutory obligations set up. Use Configure obligations to add pension, tax and levies."
				min-width="1280px"
			>
				<template #cell-obligation_name="{ row }">
					<div class="min-w-0">
						<div class="truncate font-medium text-ch-ink">{{ row.obligation_name }}</div>
						<div class="truncate text-[12px] text-ch-ink-3">{{ row.frequency }} · {{ row.liability_account }}</div>
					</div>
				</template>
				<template #cell-accruals="{ row }">
					<button v-if="row.accruals.length" type="button" class="rounded-4 border border-ch-line px-2 py-0.5 text-[12px] hover:bg-ch-hover" @click="vouchers = row.name">
						{{ row.accruals.length }} voucher{{ row.accruals.length === 1 ? "" : "s" }}
					</button>
					<span v-else class="text-ch-ink-3">—</span>
				</template>
				<template #cell-payments="{ row }">
					<button v-if="row.payments.length || row.requests.length" type="button" class="truncate text-left text-ch-ink-2 hover:text-ch-ink hover:underline" @click="vouchers = row.name">
						{{ paymentNote(row) }}
					</button>
					<span v-else class="text-ch-ink-3">Unpaid</span>
				</template>
				<template #cell-status="{ row }">
					<div class="flex flex-col items-start gap-0.5">
						<StatusBadge pill :tone="STATUS_TONES[row.status]" :status="row.status" />
						<span class="text-[12px] text-ch-ink-3">due {{ formatDateShort(row.deadline) }}</span>
					</div>
				</template>
				<template #cell-actions="{ row }">
					<div class="flex items-center justify-end gap-1.5">
						<StatusBadge v-if="row.requests.length" pill :tone="requestTone(row)" :status="`Payment ${row.requests[0].status.toLowerCase()}`" />
						<Button size="sm" icon-left="lucide-users" label="Breakdown" @click="breakdown = row as Obligation" />
						<Button
							v-if="row.balance > 0"
							size="sm"
							variant="solid"
							label="Request payment"
							:tooltip="row.open_request ? `Payment request ${row.open_request} is still open` : undefined"
							:disabled="!!row.open_request"
							@click="startRequest(row)"
						/>
					</div>
				</template>
			</DataTable>
		</section>
	</div>

	<Dialog v-model:open="requestOpen" title="Request payment">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Sends a Payment Request Form for {{ requesting?.obligation_name }} to Accounts. Once it is approved, the draft bank entry that
				pays it from the liability account is made for Accounts to submit.
			</p>
			<FormControl v-model="amount" type="number" label="Amount" />
			<LinkField v-model="account" doctype="Account" label="Pay from" required size="md" :filters="accountFilters" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="requestOpen = false" />
				<Button variant="solid" label="Request payment" :disabled="!account || !(Number(amount) > 0)" :loading="saving" @click="request" />
			</div>
		</template>
	</Dialog>

	<ObligationConfigDialog v-model:open="configOpen" :company="scope.company" @changed="reload" />
	<ObligationBreakdownDialog :scope="scope" :obligation="breakdown" @close="breakdown = null" />
	<ObligationVouchersDialog :obligation="shownVouchers" @close="vouchers = null" @changed="reload" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, FormControl, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import LinkField from "@/components/fields/LinkField.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import { REQUEST_TONES, getCompliance, requestObligationPayment, useTabData, type Obligation, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort } from "@/utils/format"
import type { Tone } from "@/utils/status"
import ObligationBreakdownDialog from "./ObligationBreakdownDialog.vue"
import ObligationConfigDialog from "./ObligationConfigDialog.vue"
import ObligationVouchersDialog from "./ObligationVouchersDialog.vue"

const props = defineProps<{ scope: Scope }>()
const { data, loading, error, reload } = useTabData(props.scope, getCompliance)

const STATUS_TONES: Record<string, Tone> = { Settled: "green", "On Track": "blue", "Due Soon": "amber", Overdue: "red" }
// Worst first, for the overall deadline card
const SEVERITY = ["Overdue", "Due Soon", "On Track", "Settled"]

const obligations = computed(() => data.value?.obligations || [])
const total = (key: "payable" | "remitted" | "balance") => obligations.value.reduce((sum, o) => sum + (o[key] || 0), 0)
const overallStatus = computed(() => SEVERITY.find((s) => obligations.value.some((o) => o.status === s)) || "Settled")

const configOpen = ref(false)
const breakdown = ref<Obligation | null>(null)
// By name, so the dialog follows the row when a request in it is approved and the tab reloads
const vouchers = ref<string | null>(null)
const shownVouchers = computed(() => obligations.value.find((o) => o.name === vouchers.value) || null)

const requestTone = (row: Record<string, any>) => REQUEST_TONES[(row as Obligation).requests[0].status]

function paymentNote(row: Record<string, any>) {
	const paid = row.payments.length ? `${row.payments.length} payment voucher${row.payments.length === 1 ? "" : "s"}` : ""
	const requested = row.requests.length ? `${row.requests.length} request${row.requests.length === 1 ? "" : "s"}` : ""
	return [paid, requested].filter(Boolean).join(" · ")
}

const requestOpen = ref(false)
const requesting = ref<Obligation | null>(null)
const amount = ref<string | number>("")
const account = ref<string | null>(null)
const saving = ref(false)
const accountFilters = computed(() => ({ company: requesting.value?.company, is_group: 0, account_type: ["in", ["Bank", "Cash"]] }))

function startRequest(row: Obligation) {
	requesting.value = row
	amount.value = row.balance
	account.value = row.payment_account
	requestOpen.value = true
}

async function request() {
	saving.value = true
	try {
		const name = await requestObligationPayment(requesting.value!.name, Number(amount.value), account.value)
		toast.success(`Payment request ${name} sent to Accounts`)
		requestOpen.value = false
		await reload()
	} finally {
		saving.value = false
	}
}

const money = (label: string, key: string): Column => ({ key, label, width: "minmax(120px,1fr)", align: "right", format: (v) => formatCurrency(v) })
const columns: Column[] = [
	{ key: "obligation_name", label: "Statutory obligation", width: "minmax(200px,1.8fr)" },
	money("Payable (Cr)", "payable"),
	{ key: "accruals", label: "Accrual vouchers", width: "130px" },
	money("Remitted (Dr)", "remitted"),
	{ key: "payments", label: "Payment details", width: "minmax(150px,1.2fr)" },
	money("Balance", "balance"),
	{ key: "status", label: "Deadline", width: "120px" },
	{ key: "actions", label: "", width: "360px", align: "right" },
]
</script>
