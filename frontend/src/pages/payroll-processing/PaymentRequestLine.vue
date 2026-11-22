<template>
	<div class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px]">
		<a :href="`/desk/payment-request-form/${encodeURIComponent(request.name)}`" target="_blank" class="font-medium text-ch-ink hover:underline">
			{{ request.name }}
		</a>
		<StatusBadge pill :tone="REQUEST_TONES[request.status]" :status="request.status" />
		<span class="tabular-nums text-ch-ink">{{ formatCurrency(request.amount, request.currency) }}</span>
		<span class="text-ch-ink-3">Requested by {{ request.requested_by_name || "—" }} on {{ formatDateShort(request.creation) }}</span>
		<span v-if="request.status === 'Rejected'" class="text-ch-red-ink">
			Rejected by {{ request.approved_by_name }}: {{ request.rejection_reason }}
		</span>
		<span v-else-if="request.approved_by_name" class="text-ch-ink-3">Approved by {{ request.approved_by_name }}</span>
		<a
			v-if="request.journal_entry"
			:href="`/desk/journal-entry/${encodeURIComponent(request.journal_entry)}`"
			target="_blank"
			class="text-ch-ink hover:underline"
		>
			Bank entry {{ request.journal_entry }}
		</a>
		<div v-if="request.can_decide" class="ml-auto flex gap-1.5">
			<Button size="sm" variant="solid" icon-left="lucide-check" label="Approve" :loading="busy" @click="confirmApprove" />
			<Button size="sm" theme="red" icon-left="lucide-x" label="Reject" :disabled="busy" @click="rejectOpen = true" />
		</div>
	</div>

	<Dialog v-model:open="rejectOpen" title="Reject payment request">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">Reject {{ request.name }}? HR can send a new request once the reason is dealt with.</p>
			<FormControl v-model="reason" type="textarea" label="Reason" :rows="3" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="rejectOpen = false" />
				<Button variant="solid" theme="red" label="Reject" :disabled="!reason.trim()" :loading="busy" @click="decide(false)" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Button, Dialog, FormControl, dialog, toast } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { REQUEST_TONES, decidePaymentRequest, type PaymentRequest } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort } from "@/utils/format"

/** A Payment Request Form in one line: its state, amount and people. Accounts approves or rejects it here. */
const props = defineProps<{ request: PaymentRequest }>()
const emit = defineEmits<{ changed: [] }>()

const busy = ref(false)
const rejectOpen = ref(false)
const reason = ref("")

function confirmApprove() {
	dialog.confirm({
		title: "Approve payment request",
		message: `Approve ${props.request.name} for ${formatCurrency(props.request.amount, props.request.currency)}?`,
		confirmLabel: "Approve",
		onConfirm: () => decide(true),
	})
}

async function decide(approve: boolean) {
	busy.value = true
	try {
		await decidePaymentRequest(props.request.name, approve, reason.value.trim())
		rejectOpen.value = false
		toast.success(approve ? "Payment request approved" : "Payment request rejected")
		emit("changed")
	} finally {
		busy.value = false
	}
}
</script>
