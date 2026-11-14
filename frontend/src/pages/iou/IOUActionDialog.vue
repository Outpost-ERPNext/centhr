<template>
	<Dialog v-model:open="isOpen" :title="title" :size="action === 'Modify' && isClaim ? '2xl' : 'lg'">
		<template #default>
			<div v-if="row" class="flex flex-col gap-4 text-[13px]">
				<!-- What is being acted on -->
				<div class="flex flex-wrap items-center justify-between gap-2 rounded-4 border border-ch-line bg-ch-subtle/50 p-3">
					<div class="min-w-0">
						<div class="font-semibold text-ch-ink">{{ row.name }}</div>
						<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee_name }} · {{ row.employee }}</div>
					</div>
					<div class="text-right">
						<div class="font-semibold tabular-nums text-ch-ink">{{ formatCurrency(row.amount) }}</div>
						<div v-if="isClaim && row.amount_from_iou" class="text-[11.5px] tabular-nums">
							<span class="text-ch-amber-ink">IOU {{ formatCurrency(row.amount_from_iou) }}</span>
							<span v-if="row.amount_from_pocket" class="text-ch-blue-ink"> · Pocket {{ formatCurrency(row.amount_from_pocket) }}</span>
						</div>
					</div>
				</div>

				<!-- Approve -->
				<p v-if="action === 'Approve'" class="text-ch-ink-2">
					{{ approveText }}
				</p>

				<!-- Reject -->
				<template v-else-if="action === 'Reject'">
					<FormControl
						v-model="reason"
						type="textarea"
						label="Reason for Rejection"
						placeholder="The employee receives this reason by email"
						:rows="3"
					/>
				</template>

				<!-- Modify -->
				<template v-else-if="action === 'Modify'">
					<FormControl
						v-if="!isClaim"
						v-model="advanceAmount"
						type="number"
						label="Modified Advance Amount"
						:placeholder="String(row.amount)"
					/>
					<div v-else class="flex flex-col gap-2">
						<div v-if="detailLoading" class="text-ch-ink-3">Loading claim rows…</div>
						<div
							v-for="line in lines"
							:key="line.name"
							class="grid grid-cols-1 items-end gap-2 rounded-3 border border-ch-line p-2.5 sm:grid-cols-[1fr_1.4fr_140px]"
						>
							<FormControl v-model="line.expense_type" type="select" label="Claim Type" :options="expenseTypes" />
							<div class="flex flex-col gap-1">
								<span class="text-[12px] text-ch-ink-3">Description</span>
								<span class="truncate text-ch-ink-2" :title="line.description">{{ line.description || "—" }}</span>
							</div>
							<FormControl v-model="line.amount" type="number" label="Amount" />
						</div>
					</div>
				</template>

				<!-- Pay -->
				<template v-else-if="action === 'Pay'">
					<p class="text-ch-ink-2">
						{{
							isClaim
								? `Pay ${formatCurrency(row.outstanding_amount || 0)} to the employee for the claim amount the IOU did not cover.`
								: "Initiate the payment on the bank page first. Once it succeeds, select the bank account and attach the payment advice."
						}}
					</p>
					<FormControl v-model="bankAccount" type="select" label="Paid From" :options="accountOptions" />
					<FormControl v-model="referenceNo" label="Bank Reference No" placeholder="Defaults to the document number" />
					<div v-if="!isClaim" class="flex flex-col gap-1">
						<span class="text-[12px] text-ch-ink-3">Payment Advice</span>
						<FileUploader :file-types="['image/*', 'application/pdf']" @success="(file: any) => (paymentAdvice = file.file_url)">
							<template #default="{ uploading, progress, openFileSelector, error: uploadError }">
								<div class="flex items-center gap-2">
									<Button
										size="sm"
										icon-left="lucide-paperclip"
										:loading="uploading"
										:label="uploading ? `Uploading ${progress}%` : paymentAdvice ? 'Replace' : 'Attach'"
										@click="openFileSelector"
									/>
									<a v-if="paymentAdvice" :href="paymentAdvice" target="_blank" class="truncate text-[12px] text-ch-primary underline">
										{{ paymentAdvice.split("/").pop() }}
									</a>
									<span v-if="uploadError" class="text-[12px] text-ch-red-ink">{{ uploadError }}</span>
								</div>
							</template>
						</FileUploader>
					</div>
				</template>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" :disabled="submitting" @click="isOpen = false" />
				<Button
					variant="solid"
					:theme="action === 'Reject' ? 'red' : 'gray'"
					:label="confirmLabel"
					:loading="submitting"
					:disabled="!canSubmit"
					@click="submit"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, FileUploader, FormControl, toast } from "frappe-ui"
import {
	applyIOUAction,
	getExpenseClaimTypes,
	getIOUDetail,
	getPaymentAccounts,
	payIOU,
	type IOUAction,
	type IOURow,
	type PaymentAccount,
} from "@/data/iou"
import { formatCurrency } from "@/utils/format"

const props = defineProps<{
	modelValue: boolean
	row: IOURow | null
	action: IOUAction | null
}>()

const emit = defineEmits<{
	"update:modelValue": [value: boolean]
	done: []
}>()

const isOpen = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
})

const isClaim = computed(() => props.row?.doctype === "Expense Claim")
const label = computed(() => (props.row?.doctype === "Employee Advance" ? "IOU" : "Claim"))
const title = computed(() => {
	if (props.action === "Pay") return `Pay ${label.value}`
	return `${props.action || ""} ${label.value}`
})
const confirmLabel = computed(() => {
	if (props.action === "Modify") return "Submit"
	if (props.action === "Reject") return "Reject"
	if (props.action === "Pay") return "Pay"
	return "Yes, Approve"
})
const approveText = computed(() => `Approve ${props.row?.name} of ${formatCurrency(props.row?.amount || 0)}?`)

const submitting = ref(false)
const reason = ref("")
const advanceAmount = ref<number | string>("")
const bankAccount = ref("")
const referenceNo = ref("")
const paymentAdvice = ref("")
const accounts = ref<PaymentAccount[]>([])
const expenseTypes = ref<string[]>([])
const lines = ref<{ name: string; expense_type: string; description?: string; amount: number; original_type: string; original_amount: number }[]>([])
const detailLoading = ref(false)

const accountOptions = computed(() => [
	{ label: "Select an account", value: "" },
	...accounts.value.map((account) => ({ label: `${account.name} (${account.account_type})`, value: account.name })),
])

const canSubmit = computed(() => {
	if (props.action === "Reject") return reason.value.trim().length > 0
	if (props.action === "Modify") return isClaim.value ? lines.value.length > 0 : Number(advanceAmount.value) > 0
	if (props.action === "Pay") return Boolean(bankAccount.value)
	return true
})

watch(
	() => [props.modelValue, props.row, props.action] as const,
	([open, row, action]) => {
		if (!open || !row) return
		reason.value = ""
		advanceAmount.value = row.amount
		bankAccount.value = ""
		referenceNo.value = ""
		paymentAdvice.value = ""
		lines.value = []
		if (action === "Pay" && row.company) loadAccounts(row.company)
		if (action === "Modify" && row.doctype === "Expense Claim") loadLines(row)
	},
	{ immediate: true }
)

async function loadAccounts(company: string) {
	accounts.value = await getPaymentAccounts(company).catch(() => [])
}

async function loadLines(row: IOURow) {
	detailLoading.value = true
	try {
		const [detail, types] = await Promise.all([getIOUDetail(row.name, row.doctype), getExpenseClaimTypes()])
		expenseTypes.value = types
		lines.value = (detail.expenses || []).map((exp: any) => ({
			name: exp.name,
			expense_type: exp.expense_type,
			description: exp.description,
			amount: exp.amount,
			original_type: exp.expense_type,
			original_amount: exp.amount,
		}))
	} finally {
		detailLoading.value = false
	}
}

async function submit() {
	const row = props.row
	const action = props.action
	if (!row || !action) return
	submitting.value = true
	try {
		if (action === "Pay") {
			const result = await payIOU(row.doctype, row.name, {
				bank_account: bankAccount.value,
				reference_no: referenceNo.value || undefined,
				payment_advice: paymentAdvice.value || undefined,
			})
			toast.success(`Paid through ${result.payment_entry}`)
		} else if (action === "Modify") {
			const expenses = lines.value
				.filter((line) => line.expense_type !== line.original_type || Number(line.amount) !== Number(line.original_amount))
				.map((line) => ({ name: line.name, expense_type: line.expense_type, amount: Number(line.amount) }))
			await applyIOUAction(row.doctype, row.name, "Modify", isClaim.value ? { expenses } : { advance_amount: Number(advanceAmount.value) })
			toast.success(`${row.name} modified`)
		} else {
			await applyIOUAction(row.doctype, row.name, action, action === "Reject" ? { reason: reason.value.trim() } : {})
			toast.success(`${row.name} ${action === "Reject" ? "rejected" : "approved"}`)
		}
		isOpen.value = false
		emit("done")
	} catch {
		// api() already showed the server's message
	} finally {
		submitting.value = false
	}
}
</script>
