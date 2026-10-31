<template>
	<DocPageShell
		doctype="Shift Assignment"
		list-label="Shift Assignment"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.employee || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="['amended_from']"
		:link-filters="linkFilters"
		:link-queries="{ employee: 'erpnext.controllers.queries.employee_query' }"
	>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				The employee works this shift from the start date until the end date, or until it is set Inactive when there
				is no end date. It takes effect once submitted.
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Assignment"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Shift', value: page.doc.value.shift_type, route: routeFor('Shift Type', page.doc.value.shift_type) },
					{ label: 'Timing', value: timing },
					{ label: 'From', value: formatDate(page.doc.value.start_date) },
					{ label: 'Until', value: page.doc.value.end_date ? formatDate(page.doc.value.end_date) : 'No end date' },
					{ label: 'Status', value: page.doc.value.status },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getList } from "@/data/list"
import { useDocPage } from "@/data/useDocPage"
import { formatDate, formatDateShort, shiftTiming } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const timing = ref("")

const page = useDocPage("Shift Assignment", props.name, {
	defaults: () => {
		const values: Record<string, any> = {}
		for (const key of ["employee", "shift_type", "company"]) if (route.query[key]) values[key] = route.query[key]
		return values
	},
	onLoaded: async (doc) => {
		if (page.isNew || !doc.shift_type) return
		// Users who cannot read Shift Type still see the assignment, without the timing
		const [shift] = await getList({
			doctype: "Shift Type",
			fields: ["start_time", "end_time"],
			filters: [["name", "=", doc.shift_type]],
			limit: 1,
			silent: true,
		}).catch(() => [])
		timing.value = shift ? shiftTiming(shift.start_time, shift.end_time) : ""
	},
})

// Only active employees of the chosen company; HRMS rejects assignments for inactive ones
const linkFilters = {
	employee: (doc: Record<string, any>) => ({ status: "Active", ...(doc.company ? { company: doc.company } : {}) }),
}

const subtitle = computed(() => {
	const d = page.doc.value
	if (page.isNew || !d.shift_type) return ""
	return `${d.shift_type} · ${formatDateShort(d.start_date)} – ${d.end_date ? formatDateShort(d.end_date) : "ongoing"}`
})
</script>
