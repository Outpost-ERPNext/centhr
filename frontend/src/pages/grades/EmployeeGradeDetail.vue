<template>
	<DocPageShell
		doctype="Employee Grade"
		list-label="Grade"
		name-label="Grade name"
		:page="page"
		:title="page.doc.value.name"
		:subtitle="page.isNew ? '' : page.doc.value.default_salary_structure || ''"
		:link-filters="linkFilters"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-award size-5" />
			</span>
		</template>
		<template #status><span /></template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Bulk Salary Structure Assignment uses the grade's default base pay for the employees of this grade.
				<template v-if="page.isNew">To rename the grade later, use Desk.</template>
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Default salary structure', value: page.doc.value.default_salary_structure },
					{
						label: 'Default base pay',
						value: page.doc.value.default_base_pay
							? formatCurrency(page.doc.value.default_base_pay, page.doc.value.currency)
							: null,
					},
					...(can('Employee').read
						? [
								{
									label: 'Active employees',
									value: String(employees),
									route: `/employees?grade=${encodeURIComponent(page.doc.value.name)}&status=Active`,
								},
							]
						: []),
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { ref } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getCount } from "@/data/list"
import { can } from "@/data/permissions"
import { useDocPage } from "@/data/useDocPage"
import { formatCurrency } from "@/utils/format"

const props = defineProps<{ name: string | null }>()
const employees = ref(0)

const page = useDocPage("Employee Grade", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew || !can("Employee").read) return
		employees.value = await getCount("Employee", [["grade", "=", doc.name], ["status", "=", "Active"]], [], true).catch(
			() => 0
		)
	},
})

// As in the HRMS Employee Grade form
const linkFilters = { default_salary_structure: () => ({ docstatus: 1, is_active: "Yes" }) }
</script>
