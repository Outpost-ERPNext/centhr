<template>
	<section class="flex flex-col gap-3 rounded-5 border border-ch-line bg-ch-surface px-4 py-3 text-[13px]">
		<div class="flex flex-wrap items-center gap-x-3 gap-y-2">
			<span class="lucide-banknote size-4 text-ch-ink-3" />
			<RouterLink :to="routeFor('Payroll Entry', run.name)!" class="font-medium text-ch-ink hover:underline">{{ run.name }}</RouterLink>
			<StatusBadge pill doctype="Payroll Entry" :status="run.status" />
			<span class="text-ch-ink-3">{{ formatNumber(run.number_of_employees) }} employees</span>

			<div class="ml-auto flex items-center gap-1.5">
				<Button
					v-if="run.next_step"
					variant="solid"
					:icon-left="STEPS[run.next_step].icon"
					:label="STEPS[run.next_step].label"
					:loading="busy"
					@click="start(run.next_step)"
				/>
				<Button
					v-if="run.has_withheld_salaries && run.payouts.length"
					:icon-left="STEPS.release_withheld.icon"
					:label="STEPS.release_withheld.label"
					:disabled="busy"
					@click="start('release_withheld')"
				/>
				<Dropdown v-if="run.docstatus === 1 && can('Payroll Entry').cancel" :options="moreOptions" align="end">
					<Button icon="lucide-ellipsis" aria-label="More payroll actions" :disabled="busy" />
				</Dropdown>
			</div>
		</div>

		<ol class="flex flex-wrap gap-x-5 gap-y-1">
			<li v-for="stage in stages(run)" :key="stage.label" class="flex items-center gap-1.5" :class="stage.done ? 'text-ch-ink' : 'text-ch-ink-3'">
				<span class="size-4" :class="stage.done ? 'lucide-circle-check text-ch-green-ink' : 'lucide-circle-dashed'" />
				{{ stage.label }}
			</li>
		</ol>

		<p v-if="run.status === 'Queued'" class="flex items-center gap-2 text-ch-amber-ink">
			<LoadingIndicator class="size-3.5" /> Working in the background. This updates by itself.
		</p>
		<p v-else-if="run.status === 'Failed' && run.error_message" class="rounded-4 bg-ch-red-bg px-3 py-2 text-ch-red-ink">
			{{ stripHtml(run.error_message) }}
		</p>
		<p v-if="run.payouts.length" class="flex flex-wrap items-center gap-2 text-ch-ink-3">
			Bank entries:
			<a v-for="je in run.payouts" :key="je.name" :href="`/desk/journal-entry/${encodeURIComponent(je.name)}`" target="_blank" class="text-ch-ink hover:underline">
				{{ je.name }} ({{ je.docstatus ? "Submitted" : "Draft" }})
			</a>
		</p>
	</section>

	<Dialog v-model:open="accountOpen" :title="pending ? STEPS[pending].label : ''">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">{{ pending && STEPS[pending].confirm }}</p>
			<LinkField v-model="account" doctype="Account" label="Pay from" required size="md" :filters="accountFilters" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="accountOpen = false" />
				<Button variant="solid" label="Continue" :disabled="!account" :loading="busy" @click="runStep(pending!)" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, Dropdown, LoadingIndicator, dialog, toast } from "frappe-ui"
import LinkField from "@/components/fields/LinkField.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { stripHtml } from "@/data/api"
import { can } from "@/data/permissions"
import { STEPS, runPayrollStep, stages, type PayrollRun, type StepKey } from "@/data/payrollRun"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ run: PayrollRun; company: string }>()
const emit = defineEmits<{ changed: [run: PayrollRun] }>()

const busy = ref(false)
const pending = ref<StepKey | null>(null)
const accountOpen = ref(false)
const account = ref<string | null>(null)

// As in the HRMS Payroll Entry form: pay out of a bank or cash ledger of the company
const accountFilters = computed(() => ({ company: props.company, is_group: 0, account_type: ["in", ["Bank", "Cash"]] }))
const moreOptions = computed(() => [{ label: STEPS.cancel.label, icon: STEPS.cancel.icon, onClick: () => start("cancel") }])

function start(step: StepKey) {
	pending.value = step
	if (STEPS[step].needsAccount) {
		account.value = props.run.payment_account
		accountOpen.value = true
		return
	}
	dialog.confirm({
		title: STEPS[step].label,
		message: STEPS[step].confirm,
		confirmLabel: STEPS[step].danger ? "Cancel payroll" : "Continue",
		theme: STEPS[step].danger ? "red" : undefined,
		onConfirm: () => runStep(step),
	})
}

async function runStep(step: StepKey) {
	busy.value = true
	try {
		const run = await runPayrollStep(props.run.name, step, STEPS[step].needsAccount ? account.value : null)
		accountOpen.value = false
		toast.success(run.status === "Queued" ? "Started in the background" : `${STEPS[step].label}: done`)
		emit("changed", run)
	} finally {
		busy.value = false
	}
}
</script>
