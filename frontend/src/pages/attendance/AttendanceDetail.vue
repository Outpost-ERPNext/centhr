<template>
	<DocPageShell
		doctype="Attendance"
		list-label="Attendance"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : formatDateShort(page.doc.value.attendance_date) + (page.doc.value.shift ? ` · ${page.doc.value.shift}` : '')"
		:hidden-fields="['naming_series', 'amended_from']"
		:link-filters="{ employee: () => ({ status: 'Active' }) }"
		@change="onChange"
	>
		<template #status>
			<span v-if="!page.isNew" class="flex items-center gap-2">
				<StatusBadge pill doctype="Attendance" :status="page.doc.value.status" />
				<StatusBadge pill :status="docstatusLabel(page.docstatus.value)" />
			</span>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Date', value: formatDate(page.doc.value.attendance_date) },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Leave type', value: page.doc.value.leave_type },
					{ label: 'Leave application', value: page.doc.value.leave_application, route: routeFor('Leave Application', page.doc.value.leave_application) },
					{ label: 'Working hours', value: page.doc.value.working_hours ? formatNumber(page.doc.value.working_hours) : null },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { formatDate, formatDateShort, formatNumber } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()

const page = useDocPage("Attendance", props.name, {
	defaults: () => (route.query.employee ? { employee: route.query.employee } : {}),
})

/** The Desk form clears the leave fields when they no longer apply. */
function onChange(fieldname: string, value: any) {
	const doc = page.doc.value
	if (fieldname === "status") {
		if (!["On Leave", "Half Day"].includes(value)) doc.leave_type = null
		if (value !== "Half Day") doc.half_day_status = null
	}
}
</script>
