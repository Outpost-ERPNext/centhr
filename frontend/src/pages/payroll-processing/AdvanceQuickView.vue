<template>
	<Dialog :open="!!name" :title="advance ? advance.employee_name : 'Employee advance'" size="2xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="advance" class="flex flex-col gap-4 text-[13px]">
			<div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-ch-ink-3">
				<span class="tabular-nums">{{ advance.name }}</span>
				<StatusBadge pill doctype="Employee Advance" :status="advance.status" />
				<StatusBadge pill :tone="DUE_TONES[advance.due_status]" :status="advance.due_status" />
				<span>{{ [advance.employee, advance.department].filter(Boolean).join(" · ") }}</span>
				<span class="ml-auto">{{ advance.company }}</span>
			</div>

			<div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
				<div v-for="item in amounts" :key="item.label" class="rounded-4 border border-ch-line px-3 py-2">
					<div class="text-[11.5px] uppercase tracking-wide text-ch-ink-3">{{ item.label }}</div>
					<div class="truncate text-[15px] font-semibold tabular-nums" :class="item.warn ? 'text-ch-amber-ink' : 'text-ch-ink'">{{ money(item.value) }}</div>
				</div>
			</div>

			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<section class="rounded-4 border border-ch-line">
					<h3 class="border-b border-ch-line px-3 py-2 font-medium text-ch-ink">Advance</h3>
					<dl class="px-3 py-1">
						<div v-for="item in facts" :key="item.label" class="flex justify-between gap-3 py-1">
							<dt class="shrink-0 text-ch-ink-3">{{ item.label }}</dt>
							<dd class="truncate text-right" :class="item.warn ? 'font-medium text-ch-amber-ink' : 'text-ch-ink'">{{ item.value || "—" }}</dd>
						</div>
					</dl>
				</section>

				<section class="rounded-4 border border-ch-line">
					<h3 class="border-b border-ch-line px-3 py-2 font-medium text-ch-ink">Settled so far</h3>
					<dl class="px-3 py-1">
						<div v-for="claim in advance.claims" :key="claim.parent" class="flex justify-between gap-3 py-1">
							<dt class="truncate text-ch-ink-2">
								Expense claim
								<a :href="`/desk/expense-claim/${encodeURIComponent(claim.parent)}`" target="_blank" class="text-ch-primary hover:underline">{{ claim.parent }}</a>
								{{ claim.docstatus ? "" : " (draft)" }}
							</dt>
							<dd class="tabular-nums text-ch-ink">{{ money(claim.allocated_amount) }}</dd>
						</div>
						<div v-for="deduction in advance.deductions" :key="deduction.name" class="flex justify-between gap-3 py-1">
							<dt class="truncate text-ch-ink-2">
								<a :href="`/desk/additional-salary/${encodeURIComponent(deduction.name)}`" target="_blank" class="text-ch-primary hover:underline">Salary deduction</a>
								{{ formatDateShort(deduction.payroll_date) }}{{ deduction.docstatus ? "" : " (draft)" }}
								<template v-if="deduction.salary_slip">
									· on slip
									<RouterLink :to="routeFor('Salary Slip', deduction.salary_slip)!" class="text-ch-primary hover:underline">{{ deduction.salary_slip }}</RouterLink>
								</template>
								<template v-else>· not on a salary slip yet</template>
							</dt>
							<dd class="tabular-nums text-ch-ink">{{ money(deduction.amount) }}</dd>
						</div>
						<p v-if="!advance.claims.length && !advance.deductions.length" class="py-2 text-ch-ink-3">
							No expense claim or salary deduction yet
						</p>
					</dl>
				</section>
			</div>

			<p class="rounded-4 px-3 py-2" :class="advance.recovery_scheduled ? 'bg-ch-blue-bg text-ch-blue-ink' : 'bg-ch-subtle text-ch-ink-2'">
				{{ advance.recovery_note }}
			</p>
		</div>
		<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>

		<template #actions>
			<div class="flex flex-wrap justify-end gap-2">
				<Button v-if="advance" icon-left="lucide-external-link" label="Open in Desk" @click="openDesk" />
				<Button
					v-if="advance && canRecover"
					variant="solid"
					icon-left="lucide-hand-coins"
					label="Recover in payroll"
					@click="$emit('recover', advance)"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, LoadingIndicator } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { getAdvanceDetails, type AdvanceDetails, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort, today } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import type { Tone } from "@/utils/status"

const DUE_TONES: Record<AdvanceDetails["due_status"], Tone> = { Overdue: "red", "Due this cycle": "amber", Upcoming: "blue", "No due date": "gray" }

/** An employee advance at a glance, without leaving the dashboard: what was paid, what is settled
 * and what is still to recover. */
const props = defineProps<{ name: string | null; /** The pay cycle its recovery is judged against. */ scope?: Scope }>()
defineEmits<{ close: []; recover: [advance: AdvanceDetails] }>()

const advance = ref<AdvanceDetails | null>(null)
watch(
	() => props.name,
	async (name) => {
		advance.value = null
		if (name) advance.value = await getAdvanceDetails(name, props.scope)
	},
	{ immediate: true }
)

const money = (value: number) => formatCurrency(value, advance.value?.currency)
const overdue = computed(() => !!advance.value?.due_date && advance.value.due_date < today() && advance.value.outstanding_amount > 0)
const canRecover = computed(
	() => !!advance.value!.repay_unclaimed_amount_from_salary && !advance.value!.recovery_scheduled && advance.value!.outstanding_amount > 0
)

const amounts = computed(() => [
	{ label: "Advance", value: advance.value!.advance_amount },
	{ label: "Paid", value: advance.value!.paid_amount },
	{ label: "Claimed + returned", value: advance.value!.claimed_amount + advance.value!.return_amount },
	{ label: "Still to recover", value: advance.value!.outstanding_amount, warn: advance.value!.outstanding_amount > 0 },
])
const facts = computed(() => [
	{ label: "Posted", value: formatDateShort(advance.value!.posting_date) },
	{ label: "Due", value: advance.value!.due_date ? `${formatDateShort(advance.value!.due_date)}${overdue.value ? " (overdue)" : ""}` : "", warn: overdue.value },
	{ label: "Purpose type", value: advance.value!.purpose_type },
	{ label: "Purpose", value: advance.value!.purpose },
	{ label: "Recover from salary", value: advance.value!.repay_unclaimed_amount_from_salary ? "Yes" : "No" },
])

function openDesk() {
	window.open(`/desk/employee-advance/${encodeURIComponent(advance.value!.name)}`, "_blank")
}
</script>
