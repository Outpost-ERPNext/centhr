<template>
	<DocPageShell
		doctype="Salary Slip"
		list-label="Salary Slip"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="['amended_from']"
	>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill doctype="Salary Slip" :status="page.doc.value.status" />
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Net pay</h3>
				<div class="text-[24px] font-semibold tabular-nums text-ch-ink">
					{{ formatCurrency(page.doc.value.rounded_total || page.doc.value.net_pay, page.doc.value.currency) || "—" }}
				</div>
				<p class="mt-1 text-[13px] tabular-nums text-ch-ink-2">
					{{ formatCurrency(page.doc.value.gross_pay, page.doc.value.currency) }} gross ·
					{{ formatCurrency(page.doc.value.total_deduction, page.doc.value.currency) }} deductions
				</p>
				<p class="mt-3 text-[12.5px] text-ch-ink-3">
					Paid for {{ formatNumber(page.doc.value.payment_days) }} of {{ formatNumber(page.doc.value.total_working_days) }} working days{{
						page.doc.value.leave_without_pay ? `, ${formatNumber(page.doc.value.leave_without_pay)} without pay` : ""
					}}.
				</p>
			</section>
			<SummaryCard
				title="Salary slip"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Salary structure', value: page.doc.value.salary_structure },
					{
						label: 'Payroll entry',
						value: page.doc.value.payroll_entry,
						route: routeFor('Payroll Entry', page.doc.value.payroll_entry),
					},
					{ label: 'Posting date', value: formatDate(page.doc.value.posting_date) },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { cycleLabel } from "@/data/payroll"
import { useDocPage } from "@/data/useDocPage"
import { formatCurrency, formatDate, formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()

const page = useDocPage("Salary Slip", props.name)

const subtitle = computed(() => {
	const d = page.doc.value
	if (page.isNew || !d.start_date) return ""
	return [cycleLabel(d.start_date, d.end_date), d.designation].filter(Boolean).join(" · ")
})
</script>
