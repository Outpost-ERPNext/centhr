<template>
	<DocPageShell
		doctype="KPI Template"
		list-label="KPI Templates"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : period"
		:link-filters="linkFilters"
	>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				The KPIs of one employee for one month. The weights add up to at most 100. Submitting the template creates the KPI Result their
				line manager fills in.
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="This month"
				:items="[
					{ label: 'Month', value: period },
					{ label: 'Line manager', value: managerName || page.doc.value.reviewer },
					{ label: 'Total weight', value: formatNumber(page.doc.value.total_weight || 0) },
					{ label: 'KPI Result', value: result ? resultLabel : 'Created on submit', route: result ? routeFor('KPI Result', result.name) : null },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getList } from "@/data/list"
import { useDocPage } from "@/data/useDocPage"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import { docstatusLabel } from "@/utils/status"

const props = defineProps<{ name: string | null }>()

const result = ref<{ name: string; docstatus: number; overall_score: number } | null>(null)
const managerName = ref("")

const page = useDocPage("KPI Template", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew) return
		const rows = await getList<{ name: string; docstatus: number; overall_score: number }>({
			doctype: "KPI Result",
			fields: ["name", "docstatus", "overall_score"],
			filters: [["kpi_template", "=", doc.name], ["docstatus", "!=", 2]],
			limit: 1,
			silent: true,
		}).catch(() => [])
		result.value = rows[0] || null
		managerName.value = doc.reviewer ? await getEmployeeName(doc.reviewer) : ""
	},
})

const period = computed(() => [page.doc.value.month, page.doc.value.fiscal_year].filter(Boolean).join(" "))
const resultLabel = computed(() =>
	result.value?.docstatus === 1 ? `Submitted · ${formatNumber(result.value.overall_score, 2)}` : docstatusLabel(result.value?.docstatus || 0)
)

const linkFilters = { employee: () => ({ status: "Active" }) }

async function getEmployeeName(employee: string) {
	const rows = await getList<{ employee_name: string }>({
		doctype: "Employee",
		fields: ["employee_name"],
		filters: [["name", "=", employee]],
		limit: 1,
		silent: true,
	}).catch(() => [])
	return rows[0]?.employee_name || ""
}
</script>
