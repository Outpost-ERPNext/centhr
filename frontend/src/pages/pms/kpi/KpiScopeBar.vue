<template>
	<div class="flex flex-wrap items-center gap-2 px-5 py-3">
		<FilterLink :model-value="scope.fiscalYear" doctype="Fiscal Year" placeholder="Fiscal year" @update:model-value="set('fiscalYear', $event)" />
		<div class="w-[calc(50%-4px)] sm:w-28">
			<Select :model-value="scope.month" :options="MONTH_OPTIONS" size="sm" aria-label="Month" @update:model-value="set('month', $event as string)" />
		</div>
		<FilterLink :model-value="scope.company" doctype="Company" placeholder="All companies" @update:model-value="setCompany" />
		<FilterLink
			:model-value="scope.department"
			doctype="Department"
			placeholder="All departments"
			:filters="scope.company ? { company: scope.company, is_group: 0 } : { is_group: 0 }"
			@update:model-value="set('department', $event)"
		/>
	</div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router"
import { Select } from "frappe-ui"
import FilterLink from "@/components/FilterLink.vue"
import { currentMonth, getCurrentFiscalYear, MONTHS, type KpiScope } from "@/data/pms"

/** The fiscal year, month, company and department the KPI pages work on. It lives in the URL, so
 * Back and a shared link show the same month. Opens on the current month. */
const scope = defineModel<KpiScope>({ required: true })
const route = useRoute()
const router = useRouter()

const MONTH_OPTIONS = MONTHS.map((month) => ({ label: month, value: month }))
const query = (key: string) => (typeof route.query[key] === "string" ? (route.query[key] as string) : "")

async function init() {
	scope.value = {
		fiscalYear: query("fy") || (await getCurrentFiscalYear()),
		month: MONTHS.includes(query("month")) ? query("month") : currentMonth(),
		company: query("company"),
		department: query("department"),
	}
}
init()

function set(key: keyof KpiScope, value: string) {
	update({ ...scope.value, [key]: value })
}

// A department belongs to one company
function setCompany(company: string) {
	update({ ...scope.value, company, department: "" })
}

function update(next: KpiScope) {
	scope.value = next
	const params = { fy: next.fiscalYear, month: next.month, company: next.company, department: next.department }
	router.replace({ query: Object.fromEntries(Object.entries(params).filter(([, value]) => value)) })
}
</script>
