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
				<Button class="ml-auto" size="sm" icon-left="lucide-settings" label="Configure obligations" @click="openDesk('/desk/statutory-obligation')" />
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
				min-width="1100px"
			>
				<template #cell-obligation_name="{ row }">
					<div class="min-w-0">
						<div class="truncate font-medium text-ch-ink">{{ row.obligation_name }}</div>
						<div class="truncate text-[12px] text-ch-ink-3">{{ row.frequency }} · {{ row.liability_account }}</div>
					</div>
				</template>
				<template #cell-accruals="{ row }">
					<a v-if="row.accruals.length" :href="ledgerRoute(row)" target="_blank" class="rounded-4 border border-ch-line px-2 py-0.5 text-[12px] hover:bg-ch-hover">
						{{ row.accruals.length }} voucher{{ row.accruals.length === 1 ? "" : "s" }} ↗
					</a>
					<span v-else class="text-ch-ink-3">—</span>
				</template>
				<template #cell-payments="{ row }">
					<span v-if="row.payments.length" class="text-ch-ink-2">{{ row.payments.map((p) => p.voucher_no).join(", ") }}</span>
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
						<a
							v-for="je in row.open_requests"
							:key="je"
							:href="`/desk/journal-entry/${encodeURIComponent(je)}`"
							target="_blank"
							class="rounded-full bg-ch-amber-bg px-2 py-0.5 text-[11.5px] text-ch-amber-ink"
							:title="`Draft payment ${je}`"
						>
							Requested ↗
						</a>
						<Button v-if="row.balance > 0" size="sm" variant="solid" label="Request payment" @click="startRequest(row)" />
					</div>
				</template>
			</DataTable>
		</section>
	</div>

	<Dialog v-model:open="requestOpen" title="Request payment">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Creates a draft bank entry paying {{ requesting?.obligation_name }} from the liability account. Accounts reviews
				and submits it.
			</p>
			<FormControl v-model="amount" type="number" label="Amount" />
			<LinkField v-model="account" doctype="Account" label="Pay from" required size="md" :filters="accountFilters" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="requestOpen = false" />
				<Button variant="solid" label="Create draft" :disabled="!account || !(Number(amount) > 0)" :loading="saving" @click="request" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, FormControl, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import LinkField from "@/components/fields/LinkField.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { cycleLabel } from "@/data/payroll"
import { getCompliance, requestObligationPayment, useTabData, type Obligation, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort } from "@/utils/format"
import type { Tone } from "@/utils/status"

const props = defineProps<{ scope: Scope }>()
const { data, loading, error, reload } = useTabData(props.scope, getCompliance)

const STATUS_TONES: Record<string, Tone> = { Settled: "green", "On Track": "blue", "Due Soon": "amber", Overdue: "red" }
// Worst first, for the overall deadline card
const SEVERITY = ["Overdue", "Due Soon", "On Track", "Settled"]

const obligations = computed(() => data.value?.obligations || [])
const total = (key: "payable" | "remitted" | "balance") => obligations.value.reduce((sum, o) => sum + (o[key] || 0), 0)
const overallStatus = computed(() => SEVERITY.find((s) => obligations.value.some((o) => o.status === s)) || "Settled")

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
		toast.success(`Draft payment ${name} created`)
		requestOpen.value = false
		await reload()
	} finally {
		saving.value = false
	}
}

function ledgerRoute(row: Obligation) {
	const query = new URLSearchParams({ company: row.company, account: JSON.stringify([row.liability_account]), from_date: props.scope.from, to_date: props.scope.to })
	return `/desk/query-report/General Ledger?${query}`
}

function openDesk(path: string) {
	window.open(path, "_blank")
}

const money = (label: string, key: string): Column => ({ key, label, width: "minmax(120px,1fr)", align: "right", format: (v) => formatCurrency(v) })
const columns: Column[] = [
	{ key: "obligation_name", label: "Statutory obligation", width: "minmax(200px,1.8fr)" },
	money("Payable (Cr)", "payable"),
	{ key: "accruals", label: "Accrual vouchers", width: "130px" },
	money("Remitted (Dr)", "remitted"),
	{ key: "payments", label: "Payment details", width: "minmax(120px,1fr)" },
	money("Balance", "balance"),
	{ key: "status", label: "Deadline", width: "120px" },
	{ key: "actions", label: "", width: "220px", align: "right" },
]
</script>
