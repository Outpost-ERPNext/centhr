<template>
	<DocPageShell
		doctype="Salary Structure"
		list-label="Salary Structure"
		:page="page"
		:title="page.doc.value.name"
		:subtitle="page.isNew ? '' : [page.doc.value.company, page.doc.value.payroll_frequency, page.doc.value.currency].filter(Boolean).join(' · ')"
		:hidden-fields="['amended_from']"
		:link-filters="linkFilters"
		name-label="Structure name"
	>
		<template #status>
			<div v-if="!page.isNew" class="flex items-center gap-1.5">
				<StatusBadge v-if="page.doc.value.is_active === 'No'" pill tone="red" status="Inactive" />
				<StatusBadge pill :status="docstatusLabel(page.docstatus.value)" />
			</div>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Assignments"
				:items="[
					{ label: 'Employees assigned', value: assigned, route: assignmentsRoute },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Frequency', value: page.doc.value.payroll_frequency },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getCount } from "@/data/list"
import { useDocPage } from "@/data/useDocPage"
import { docstatusLabel } from "@/utils/status"

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const assigned = ref(0)

const page = useDocPage("Salary Structure", props.name, {
	defaults: () => (route.query.company ? { company: route.query.company } : {}),
	onLoaded: async (doc) => {
		if (page.isNew) return
		assigned.value = await getCount("Salary Structure Assignment", [["salary_structure", "=", doc.name], ["docstatus", "=", 1]], [], true).catch(() => 0)
	},
})

// The employee overview of this structure's company, filtered to it
const assignmentsRoute = computed(() => {
	const d = page.doc.value
	return `/salary-structure-assignments?view=assigned&structure=${encodeURIComponent(d.name)}&company=${encodeURIComponent(d.company || "")}`
})

// As in the HRMS Salary Structure form
const linkFilters = {
	payment_account: (doc: Record<string, any>) => ({ company: doc.company, is_group: 0, account_type: ["in", ["Bank", "Cash"]] }),
}
</script>
