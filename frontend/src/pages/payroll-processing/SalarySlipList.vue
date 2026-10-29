<template>
	<PageHeader :crumbs="[{ label: 'Salary Slip' }]">
		<template #actions>
			<Button
				v-if="can('Salary Slip').create"
				variant="solid"
				icon-left="lucide-upload"
				label="Import from Excel"
				@click="importOpen = true"
			/>
		</template>
	</PageHeader>

	<SalaryOverviewView :overview="overview" :columns="columns">
		<template #actions="{ row }">
			<Button v-if="row.salary_slip" size="sm" label="Open slip" :route="routeFor('Salary Slip', row.salary_slip)!" />
		</template>
	</SalaryOverviewView>

	<SalarySlipImportDialog v-model:open="importOpen" @imported="overview.load" />
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import SalaryOverviewView from "@/components/SalaryOverviewView.vue"
import SalarySlipImportDialog from "./SalarySlipImportDialog.vue"
import { can } from "@/data/permissions"
import { COLUMNS } from "@/data/salaryOverview"
import { useSalaryOverview } from "@/data/useSalaryOverview"
import { routeFor } from "@/utils/routes"

const overview = useSalaryOverview()
const importOpen = ref(false)

const columns = [
	COLUMNS.name,
	COLUMNS.employee_name,
	COLUMNS.department,
	COLUMNS.gross_pay,
	COLUMNS.total_deduction,
	COLUMNS.net_pay,
	COLUMNS.slip_status,
	{ ...COLUMNS.actions, width: "190px" },
]
</script>
