<template>
	<Dialog :open="!!employee" :title="data?.employee_name || 'Employee'" size="2xl" @update:open="(value: boolean) => !value && $emit('close')">
		<div v-if="data" class="flex flex-col gap-4 text-[13px]">
			<div class="flex items-center gap-3">
				<Avatar :image="data.image || undefined" :label="data.employee_name" size="2xl" shape="square" />
				<div class="min-w-0 flex-1">
					<div class="truncate text-[12.5px] tabular-nums text-ch-ink-3">{{ data.name }}</div>
					<div class="truncate text-ch-ink-2">{{ [data.designation, data.department].filter(Boolean).join(" · ") || "No designation or department" }}</div>
					<div class="truncate text-ch-ink-3">{{ data.company }}</div>
				</div>
				<StatusBadge pill doctype="Employee" :status="data.status" />
			</div>

			<div class="grid grid-cols-2 gap-3">
				<StatCard label="Monthly base salary" :value="baseSalary" :tone="data.assignment ? 'green' : undefined" />
				<StatCard :label="from ? 'Cycle payroll status' : 'Latest payroll status'" :value="payrollStatus" :tone="payrollTone" />
			</div>

			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<section v-for="group in groups" :key="group.title" class="rounded-4 border border-ch-line">
					<h3 class="flex items-center justify-between gap-2 border-b border-ch-line px-3 py-2 font-medium text-ch-ink">
						{{ group.title }}
						<StatusBadge v-if="group.badge" pill tone="red" :status="group.badge" />
					</h3>
					<dl class="px-3 py-1">
						<div v-for="item in group.items" :key="item.label" class="flex justify-between gap-3 py-1">
							<dt class="shrink-0 text-ch-ink-3">{{ item.label }}</dt>
							<dd class="truncate text-right" :class="item.warn ? 'font-medium text-ch-amber-ink' : 'text-ch-ink'">{{ item.value || "—" }}</dd>
						</div>
					</dl>
				</section>
			</div>
		</div>
		<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>

		<template #actions>
			<div v-if="data" class="flex flex-wrap justify-end gap-2">
				<Button v-if="data.salary_slip" icon-left="lucide-receipt" label="Salary slip" :route="routeFor('Salary Slip', data.salary_slip.name)!" />
				<Button :variant="canAssign ? 'subtle' : 'solid'" icon-left="lucide-user" label="Employee master" :route="routeFor('Employee', data.name)!" />
				<Button
					v-if="canAssign"
					variant="solid"
					icon-left="lucide-plus"
					label="Assign structure"
					:route="{ name: 'SalaryStructureAssignmentNew', query: { company: data.company, employee: data.name } }"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Avatar, Button, Dialog, LoadingIndicator } from "frappe-ui"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { api } from "@/data/api"
import { can } from "@/data/permissions"
import { formatCurrency, formatDateShort } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import { toneFor } from "@/utils/status"

/** An employee at a glance, without leaving the list: base salary, payroll status, salary structure,
 * bank details, employment and the salary slip of the pay cycle (the latest slip when no cycle is given). */
const props = defineProps<{ employee: string | null; from?: string; to?: string }>()
defineEmits<{ close: [] }>()

const data = ref<Record<string, any> | null>(null)
watch(
	() => props.employee,
	async (employee) => {
		data.value = null
		if (!employee) return
		data.value = await api("centhr.api.employee.get_quick_view", {
			employee,
			from_date: props.from || undefined,
			to_date: props.to || undefined,
		})
	},
	{ immediate: true }
)

const money = (value: number, currency?: string) => formatCurrency(value, currency)

const baseSalary = computed(() => {
	const assignment = data.value!.assignment
	return assignment ? money(assignment.base, assignment.currency) : "—"
})
const payrollStatus = computed(() => data.value!.salary_slip?.status || "Pending")
const payrollTone = computed(() => (data.value!.salary_slip ? toneFor("Salary Slip", payrollStatus.value) : "amber"))
const canAssign = computed(
	() => !data.value!.assignment && data.value!.status === "Active" && can("Salary Structure Assignment").create
)

interface Group {
	title: string
	badge?: string
	items: { label: string; value?: string | null; warn?: boolean }[]
}

const groups = computed<Group[]>(() => {
	const d = data.value!
	const assignment = d.assignment
	const slip = d.salary_slip
	return [
		{
			title: "Salary structure",
			badge: assignment ? undefined : "Missing assignment",
			items: [
				{ label: "Structure name", value: assignment?.salary_structure || "None" },
				{ label: "Effective date", value: assignment && formatDateShort(assignment.from_date) },
			],
		},
		{
			title: "Banking & payment details",
			items: [
				{ label: "Bank name", value: d.bank_name || "Not configured", warn: !d.bank_name },
				{ label: "Account number", value: d.bank_ac_no },
				{ label: "Payment mode", value: d.salary_mode },
				{ label: "Payable account", value: d.payable_account },
			],
		},
		{
			title: "Employment details",
			items: [
				{ label: "Joined", value: d.date_of_joining && formatDateShort(d.date_of_joining) },
				...(d.relieving_date ? [{ label: "Relieved", value: formatDateShort(d.relieving_date) }] : []),
				{ label: "Line manager", value: d.custom_no_line_manager ? "None" : d.reports_to_name || d.reports_to },
				{ label: "Grade", value: d.grade },
				{ label: "Branch", value: d.branch },
				{ label: "Employment type", value: d.employment_type },
			],
		},
		{
			title: props.from ? "Salary slip of this cycle" : "Latest salary slip",
			items: slip
				? [
						{ label: "Period", value: `${formatDateShort(slip.start_date)} → ${formatDateShort(slip.end_date)}` },
						{ label: "Gross pay", value: money(slip.gross_pay, slip.currency) },
						{ label: "Deductions", value: money(slip.total_deduction, slip.currency) },
						{ label: "Net pay", value: money(slip.net_pay, slip.currency) },
					]
				: [{ label: "Status", value: "No salary slip" }],
		},
		{
			title: "Contact",
			items: [
				{ label: "Work email", value: d.company_email },
				{ label: "Personal email", value: d.personal_email },
				{ label: "Mobile", value: d.cell_number },
			],
		},
	]
})
</script>
