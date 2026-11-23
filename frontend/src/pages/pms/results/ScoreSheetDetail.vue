<template>
	<DocPageShell
		doctype="PMS Score Sheet"
		list-label="Score Sheets"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : `${page.doc.value.quarter} ${page.doc.value.fiscal_year}`"
		:link-filters="linkFilters"
		@change="onChange"
	>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill :tone="STATUS_TONES[page.doc.value.status] || 'gray'" :status="page.doc.value.status" />
		</template>
		<template v-if="page.editing.value" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				The outcome, increment and new CTC are worked out when you save, from the company's increment bands. Tick Normalize Score to use
				your own score for them. Submitting approves the sheet.
			</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useEmployeeDetails } from "@/data/employeeDetails"
import { useDocPage } from "@/data/useDocPage"
import type { Tone } from "@/utils/status"

const STATUS_TONES: Record<string, Tone> = { Pending: "amber", Approved: "green", Rejected: "red" }

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Score Sheet", props.name)
const { linkFilters, onChange } = useEmployeeDetails(page.doc, { employee_name: "employee_name", department: "department" })
</script>
