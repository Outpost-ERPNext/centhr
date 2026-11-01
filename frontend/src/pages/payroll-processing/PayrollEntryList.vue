<template>
	<PageHeader :crumbs="[{ label: 'Payroll Entry' }]">
		<template #actions>
			<Button
				v-if="canGenerate && !companyRun"
				variant="solid"
				icon-left="lucide-play"
				label="Generate payroll"
				:tooltip="state.company ? undefined : 'Choose a company to generate its payroll'"
				:loading="generating"
				:disabled="!state.company || !eligible.length"
				@click="confirmGenerate"
			/>
		</template>
	</PageHeader>

	<SalaryOverviewView :overview="overview" :columns="columns" audit>
		<template #toolbar>
			<CollapsibleSection v-if="runs.length" title="Payroll runs" storage-key="payroll-runs" :summary="`${runs.length} in this period`">
				<div class="flex flex-col gap-2">
					<PayrollRunCard v-for="run in runs" :key="run.name" :run="run" @changed="refresh" />
				</div>
			</CollapsibleSection>
		</template>
	</SalaryOverviewView>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { Button, dialog, toast } from "frappe-ui"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import PageHeader from "@/components/layout/PageHeader.vue"
import SalaryOverviewView from "@/components/SalaryOverviewView.vue"
import PayrollRunCard from "./PayrollRunCard.vue"
import { cycleLabel } from "@/data/payroll"
import { generatePayroll, getPayrollRuns, type PayrollRun } from "@/data/payrollRun"
import { can } from "@/data/permissions"
import { COLUMNS } from "@/data/salaryOverview"
import { useSalaryOverview } from "@/data/useSalaryOverview"
import { formatNumber } from "@/utils/format"

const POLL_MS = 3000

const overview = useSalaryOverview("payroll")
const { state, rows } = overview

const runs = ref<PayrollRun[]>([])
const generating = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | undefined

const canGenerate = computed(() => can("Payroll Entry").create && can("Payroll Entry").submit)
const companyRun = computed(() => !!state.company && runs.value.some((r) => r.company === state.company))
// Who a payroll run pays: active employees with a salary structure and no slip in the period yet
const eligible = computed(() => rows.value.filter((r) => r.status === "Active" && r.assignment && !r.salary_slip))

watch([() => state.company, () => state.from, () => state.to], loadRuns, { immediate: true })
onBeforeUnmount(() => clearTimeout(pollTimer))

async function loadRuns() {
	clearTimeout(pollTimer)
	if (!state.from || !state.to) return (runs.value = [])
	runs.value = await getPayrollRuns(state.company, state.from, state.to).catch(() => [])
	// HRMS creates and submits slips in a background job for large payrolls; follow it until it ends
	if (runs.value.some((r) => r.status === "Queued")) pollTimer = setTimeout(refresh, POLL_MS)
}

/** After a step the slips changed too, so both the runs and the employee table reload. */
function refresh() {
	return Promise.all([loadRuns(), overview.load()])
}

function confirmGenerate() {
	dialog.confirm({
		title: "Generate payroll",
		message: `Create the payroll for ${state.company}, ${cycleLabel(state.from, state.to)}? A payroll entry is submitted and draft salary slips are created for ${formatNumber(eligible.value.length)} employees with a salary structure. Review the pre-audit checks first.`,
		confirmLabel: "Generate",
		onConfirm: generate,
	})
}

async function generate() {
	generating.value = true
	try {
		const run = await generatePayroll(state.company, state.from, state.to)
		toast.success(`Payroll entry ${run.name} created`)
		await refresh()
	} finally {
		generating.value = false
	}
}

const columns = [
	COLUMNS.name,
	COLUMNS.employee_name,
	COLUMNS.department,
	COLUMNS.designation,
	COLUMNS.base,
	COLUMNS.slip_status,
	{ ...COLUMNS.actions, width: "100px" },
]
</script>
