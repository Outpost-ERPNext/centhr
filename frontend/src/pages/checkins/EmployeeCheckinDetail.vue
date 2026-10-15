<template>
	<DocPageShell
		doctype="Employee Checkin"
		list-label="Employee Checkin"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.employee || page.doc.value.name"
		:subtitle="page.isNew ? '' : [page.doc.value.log_type, formatDateTime(page.doc.value.time)].filter(Boolean).join(' · ')"
		:hidden-fields="hiddenFields"
		:link-filters="{ employee: () => ({ status: 'Active' }) }"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-fingerprint size-5" />
			</span>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew && page.doc.value.log_type" pill doctype="Employee Checkin" :status="page.doc.value.log_type" />
			<span v-else />
		</template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Logs an IN or OUT punch for the employee. The shift is set from the employee's shift assignment when saved,
				and attendance is marked from check-ins unless auto attendance is skipped.
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Time', value: formatDateTime(page.doc.value.time) },
					{ label: 'Shift', value: page.doc.value.shift || 'No shift', route: routeFor('Shift Type', page.doc.value.shift) },
					{ label: 'Device', value: page.doc.value.device_id },
					{ label: 'Attendance', value: page.doc.value.attendance, route: routeFor('Attendance', page.doc.value.attendance) },
					{ label: 'Auto attendance', value: page.doc.value.skip_auto_attendance ? 'Skipped' : 'Included' },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { formatDateTime } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()

const page = useDocPage("Employee Checkin", props.name, {
	defaults: () => ({ log_type: "IN", ...(route.query.employee ? { employee: route.query.employee } : {}) }),
})

// The location fields are only filled when HR Settings tracks geolocation; shift and attendance are set by the server
const hiddenFields = computed(() => [
	"geolocation",
	...(page.doc.value.latitude || page.doc.value.longitude ? [] : ["latitude", "longitude"]),
	...(page.isNew ? ["shift", "attendance"] : []),
])
</script>
