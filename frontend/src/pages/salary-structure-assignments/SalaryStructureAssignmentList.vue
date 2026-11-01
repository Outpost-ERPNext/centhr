<template>
	<PageHeader :crumbs="[{ label: 'Salary Structure Assignment' }]">
		<template #actions>
			<Button
				v-if="canCreate"
				variant="solid"
				icon-left="lucide-plus"
				label="New assignment"
				:route="{ name: 'SalaryStructureAssignmentNew', query: overview.state.company ? { company: overview.state.company } : {} }"
			/>
		</template>
	</PageHeader>

	<SalaryOverviewView :overview="overview" :columns="columns">
		<template #actions="{ row }">
			<Button v-if="row.assignment" size="sm" label="Edit" :route="`/salary-structure-assignments/${encodeURIComponent(row.assignment)}`" />
			<Button
				v-else-if="canCreate"
				size="sm"
				label="Assign"
				:route="{ name: 'SalaryStructureAssignmentNew', query: { company: row.company, employee: row.name } }"
			/>
		</template>
	</SalaryOverviewView>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import SalaryOverviewView from "@/components/SalaryOverviewView.vue"
import { can } from "@/data/permissions"
import { COLUMNS } from "@/data/salaryOverview"
import { useSalaryOverview } from "@/data/useSalaryOverview"

const overview = useSalaryOverview("assignments")
const canCreate = can("Salary Structure Assignment").create

const columns = [
	COLUMNS.name,
	COLUMNS.employee_name,
	COLUMNS.department,
	COLUMNS.salary_structure,
	COLUMNS.base,
	COLUMNS.effective_from,
	COLUMNS.slip_status,
	COLUMNS.actions,
]
</script>
