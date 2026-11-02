<template>
	<PageHeader :crumbs="[{ label: 'Salary Structure Assignment' }]">
		<template #actions>
			<Button
				v-for="link in links"
				:key="link.label"
				:icon-left="link.icon"
				:label="link.label"
				class="hidden md:inline-flex"
				:route="{ name: link.routeName }"
			/>
			<!-- Four labelled buttons do not fit in the header on small screens -->
			<div v-if="linkOptions.length" class="md:hidden">
				<Dropdown :options="linkOptions" align="end">
					<Button icon="lucide-ellipsis" aria-label="Salary structure actions" />
				</Dropdown>
			</div>
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
import { useRouter } from "vue-router"
import { Button, Dropdown } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import SalaryOverviewView from "@/components/SalaryOverviewView.vue"
import { can } from "@/data/permissions"
import { COLUMNS } from "@/data/salaryOverview"
import { useSalaryOverview } from "@/data/useSalaryOverview"

const overview = useSalaryOverview("assignments")
const canCreate = can("Salary Structure Assignment").create

const router = useRouter()
const links = [
	{ label: "Bulk Assign", icon: "lucide-users-round", routeName: "BulkSalaryStructureAssignment", allowed: can("Bulk Salary Structure Assignment").write },
	{ label: "Salary Structure", icon: "lucide-layers", routeName: "SalaryStructureList", allowed: can("Salary Structure").read },
	{ label: "Salary Component", icon: "lucide-list-plus", routeName: "SalaryComponentList", allowed: can("Salary Component").read },
].filter((link) => link.allowed)
const linkOptions = links.map((link) => ({
	label: link.label,
	icon: link.icon,
	onClick: () => router.push({ name: link.routeName }),
}))

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
