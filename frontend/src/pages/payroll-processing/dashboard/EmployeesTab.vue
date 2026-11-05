<template>
	<SalaryOverviewView :overview="overview" :columns="columns" hide-scope />
</template>

<script setup lang="ts">
import SalaryOverviewView from "@/components/SalaryOverviewView.vue"
import type { Scope } from "@/data/payrollDashboard"
import { COLUMNS } from "@/data/salaryOverview"
import type { SalaryOverview } from "@/data/useSalaryOverview"

/** The dashboard's employees with their structure and payroll status; it shares the dashboard's company and cycle. */
defineProps<{ scope: Scope; overview: SalaryOverview }>()

const columns = [
	COLUMNS.name,
	COLUMNS.employee_name,
	COLUMNS.department,
	COLUMNS.designation,
	COLUMNS.salary_structure,
	COLUMNS.base,
	COLUMNS.slip_status,
	{ ...COLUMNS.actions, width: "100px" },
]
</script>
