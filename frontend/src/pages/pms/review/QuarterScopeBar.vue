<template>
	<div class="flex flex-wrap items-center gap-2 px-5 py-3">
		<FilterLink :model-value="scope.fiscalYear" doctype="Fiscal Year" placeholder="Fiscal year" @update:model-value="set('fiscalYear', $event)" />
		<div class="w-[calc(50%-4px)] sm:w-24">
			<Select :model-value="scope.quarter" :options="QUARTER_OPTIONS" size="sm" aria-label="Quarter" @update:model-value="set('quarter', $event as string)" />
		</div>
		<FilterLink :model-value="scope.company" doctype="Company" :placeholder="companyRequired ? 'Company' : 'All companies'" @update:model-value="setCompany" />
		<FilterLink
			:model-value="scope.department"
			doctype="Department"
			placeholder="All departments"
			:filters="scope.company ? { company: scope.company, is_group: 0 } : { is_group: 0 }"
			@update:model-value="set('department', $event)"
		/>
		<slot />
	</div>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from "vue-router"
import { Select } from "frappe-ui"
import FilterLink from "@/components/FilterLink.vue"
import { getCurrentFiscalYear } from "@/data/pms"
import { currentQuarter, QUARTERS, type QuarterScope } from "@/data/pmsReview"

/** The fiscal year, quarter, company and department the 360 review pages work on. It lives in the
 * URL, so Back and a shared link show the same quarter. Opens on the current quarter. */
const scope = defineModel<QuarterScope>({ required: true })
defineProps<{ companyRequired?: boolean }>()
const route = useRoute()
const router = useRouter()

const QUARTER_OPTIONS = Object.keys(QUARTERS).map((quarter) => ({ label: quarter, value: quarter }))
const query = (key: string) => (typeof route.query[key] === "string" ? (route.query[key] as string) : "")

async function init() {
	scope.value = {
		fiscalYear: query("fy") || (await getCurrentFiscalYear()),
		quarter: QUARTERS[query("quarter")] ? query("quarter") : currentQuarter(),
		company: query("company"),
		department: query("department"),
	}
}
init()

function set(key: keyof QuarterScope, value: string) {
	update({ ...scope.value, [key]: value })
}

// A department belongs to one company
function setCompany(company: string) {
	update({ ...scope.value, company, department: "" })
}

function update(next: QuarterScope) {
	scope.value = next
	const params = { fy: next.fiscalYear, quarter: next.quarter, company: next.company, department: next.department }
	const merged = { ...route.query, ...params }
	router.replace({ query: Object.fromEntries(Object.entries(merged).filter(([, value]) => value)) })
}
</script>
