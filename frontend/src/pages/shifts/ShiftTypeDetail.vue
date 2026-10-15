<template>
	<DocPageShell
		doctype="Shift Type"
		list-label="Shift"
		name-label="Shift name"
		:page="page"
		:title="page.doc.value.name"
		:subtitle="page.isNew ? '' : shiftTiming(page.doc.value.start_time, page.doc.value.end_time)"
		:hidden-fields="hiddenFields"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-timer size-5" />
			</span>
		</template>
		<template #status>
			<span
				v-if="!page.isNew && page.doc.value.enable_auto_attendance"
				class="inline-flex items-center gap-1.5 rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] text-ch-ink-2"
			>
				<span class="size-2 rounded-full bg-ch-green-dot" />
				Auto attendance
			</span>
			<span v-else />
		</template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				A shift sets working hours. Employees get it through a Shift Assignment, and weekly offs come from the holiday
				list, or from the employee's or company's default when it is empty.
				<template v-if="page.isNew">The name can't be changed after the shift is created.</template>
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Timing', value: shiftTiming(page.doc.value.start_time, page.doc.value.end_time) },
					{ label: 'Holiday list', value: page.doc.value.holiday_list || 'Employee / company default' },
					...(can('Shift Assignment').read
						? [
								{ label: 'Assigned employees', value: String(summary.employees) },
								{ label: 'Entities', value: summary.companies.join(', ') || '—' },
							]
						: []),
					{ label: 'Auto attendance', value: page.doc.value.enable_auto_attendance ? 'On' : 'Off' },
					{ label: 'Roster colour', value: page.doc.value.color },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, reactive } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { can } from "@/data/permissions"
import { getShiftAssignmentSummary } from "@/data/shift"
import { useDocPage } from "@/data/useDocPage"
import { shiftTiming } from "@/utils/format"

const props = defineProps<{ name: string | null }>()
const summary = reactive({ employees: 0, companies: [] as string[] })

const page = useDocPage("Shift Type", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew) return
		const res = (await getShiftAssignmentSummary([doc.name]))[doc.name]
		summary.employees = res?.employees || 0
		summary.companies = res?.companies || []
	},
})

// The check-in sync fields only matter once auto attendance is on
const hiddenFields = computed(() =>
	page.doc.value.enable_auto_attendance ? [] : ["last_sync_of_checkin", "auto_update_last_sync"]
)
</script>
