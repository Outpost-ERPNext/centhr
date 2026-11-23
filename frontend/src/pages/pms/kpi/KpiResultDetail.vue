<template>
	<DocPageShell
		doctype="KPI Result"
		list-label="KPI Results"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="period"
		:fixed-tables="['items']"
	>
		<template v-if="page.editing.value" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Enter what was achieved for each KPI. Tick Not Measured / N/A when there is nothing to report for one. The score is worked out when
				you save; submit once every KPI is filled in.
			</p>
		</template>
		<template v-if="!page.editing.value" #aside>
			<SummaryCard
				title="Score"
				:items="[
					{ label: 'Month', value: period },
					{ label: 'Monthly KPI score', value: formatNumber(page.doc.value.overall_score || 0, 2) },
					{ label: 'Remark', value: page.doc.value.remark },
					{ label: 'KPI Template', value: page.doc.value.kpi_template, route: routeFor('KPI Template', page.doc.value.kpi_template) },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string }>()
const page = useDocPage("KPI Result", props.name)

const period = computed(() => [page.doc.value.month, page.doc.value.fiscal_year].filter(Boolean).join(" "))
</script>
