<template>
	<div class="flex flex-col gap-3 px-5 py-3">
		<div class="grid grid-cols-2 gap-2 xl:grid-cols-4">
			<StatCard label="Pending advances" :value="`${advances.length}`" :loading="loading" />
			<StatCard label="Unrecovered amount" :value="formatCurrency(sum(advances, 'pending_amount'))" tone="amber" :loading="loading" />
			<StatCard label="Deductions this cycle" :value="`${deductions.length}`" :loading="loading" />
			<StatCard label="Deducted this cycle" :value="formatCurrency(sum(deductions, 'amount'))" tone="red" :loading="loading" />
		</div>

		<section class="rounded-5 border border-ch-line bg-ch-surface">
			<header class="flex flex-wrap items-center gap-2 border-b border-ch-line px-4 py-2.5">
				<h3 class="text-[14px] font-medium text-ch-ink">Pending employee advances</h3>
				<span class="text-[12.5px] text-ch-ink-3">Paid, not yet settled by an expense claim, a return or payroll</span>
			</header>
			<DataTable :columns="advanceColumns" :rows="advances" :loading="loading" :error="error" empty-icon="lucide-hand-coins" empty-message="No unrecovered advances" min-width="900px" @row-click="(row) => openDesk('employee-advance', row.name)">
				<template #cell-employee_name="{ row }">
					<div class="min-w-0">
						<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
						<div class="truncate text-[12px] text-ch-ink-3">{{ row.employee }} · {{ row.name }}</div>
					</div>
				</template>
				<template #cell-state="{ row }">
					<StatusBadge pill :tone="row.recovery_scheduled ? 'blue' : row.overdue ? 'amber' : 'gray'" :status="row.recovery_scheduled ? 'Recovery scheduled' : row.overdue ? 'Due this cycle' : 'Upcoming'" />
				</template>
				<template #cell-actions="{ row }">
					<div class="flex justify-end" @click.stop>
						<Button
							v-if="row.repay_unclaimed_amount_from_salary && !row.recovery_scheduled"
							size="sm"
							label="Recover in payroll"
							@click="startRecovery(row)"
						/>
					</div>
				</template>
			</DataTable>
		</section>

		<section class="rounded-5 border border-ch-line bg-ch-surface">
			<header class="flex items-center gap-2 border-b border-ch-line px-4 py-2.5">
				<h3 class="text-[14px] font-medium text-ch-ink">Deductions this cycle</h3>
				<span class="text-[12.5px] text-ch-ink-3">Additional Salary deductions dated in the cycle</span>
			</header>
			<DataTable :columns="deductionColumns" :rows="deductions" :loading="loading" empty-icon="lucide-minus-circle" empty-message="No deductions in this cycle" min-width="760px" @row-click="(row) => openDesk('additional-salary', row.name)">
				<template #cell-ref_docname="{ row }">
					<span class="text-ch-ink-2">{{ row.ref_docname || "—" }}</span>
				</template>
			</DataTable>
		</section>
	</div>

	<Dialog v-model:open="recoverOpen" title="Recover advance in payroll">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Deducts {{ recovering && formatCurrency(recovering.pending_amount, recovering.currency) }} from
				{{ recovering?.employee_name }}'s salary in this cycle, as an Additional Salary.
			</p>
			<LinkField v-model="component" doctype="Salary Component" label="Deduction component" required size="md" :filters="{ type: 'Deduction', disabled: 0 }" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="recoverOpen = false" />
				<Button variant="solid" label="Recover" :disabled="!component" :loading="saving" @click="recover" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import LinkField from "@/components/fields/LinkField.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getAdvances, recoverAdvance, useTabData, type Scope } from "@/data/payrollDashboard"
import { formatCurrency, formatDateShort } from "@/utils/format"

const props = defineProps<{ scope: Scope }>()
const { data, loading, error, reload } = useTabData(props.scope, getAdvances)

const advances = computed(() => data.value?.advances || [])
const deductions = computed(() => data.value?.deductions || [])
const sum = (rows: Record<string, any>[], key: string) => rows.reduce((total, r) => total + (r[key] || 0), 0)

const recoverOpen = ref(false)
const recovering = ref<Record<string, any> | null>(null)
const component = ref<string | null>(null)
const saving = ref(false)

function openDesk(route: string, name: string) {
	window.open(`/desk/${route}/${encodeURIComponent(name)}`, "_blank")
}

function startRecovery(row: Record<string, any>) {
	recovering.value = row
	component.value = null
	recoverOpen.value = true
}

async function recover() {
	saving.value = true
	try {
		const name = await recoverAdvance(recovering.value!.name, component.value!, props.scope.to)
		toast.success(`Deduction ${name} added to this cycle`)
		recoverOpen.value = false
		await reload()
	} finally {
		saving.value = false
	}
}

const money = (label: string, key: string): Column => ({ key, label, width: "minmax(110px,1fr)", align: "right", format: (v, r) => formatCurrency(v, r.currency) })
const advanceColumns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,1.8fr)" },
	{ key: "posting_date", label: "Date", width: "100px", format: (v) => formatDateShort(v) },
	money("Advance", "advance_amount"),
	money("Paid", "paid_amount"),
	money("Pending", "pending_amount"),
	{ key: "state", label: "Status", width: "150px" },
	{ key: "actions", label: "", width: "150px", align: "right" },
]
const deductionColumns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(200px,1.8fr)", class: "font-medium" },
	{ key: "salary_component", label: "Component", width: "minmax(140px,1.2fr)" },
	{ key: "ref_docname", label: "Employee advance", width: "minmax(140px,1.2fr)" },
	{ key: "payroll_date", label: "Payroll date", width: "110px", format: (v) => formatDateShort(v) },
	money("Amount", "amount"),
]
</script>
