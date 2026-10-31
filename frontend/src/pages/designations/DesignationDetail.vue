<template>
	<DocPageShell
		doctype="Designation"
		list-label="Designation"
		:page="page"
		:title="page.doc.value.designation_name || page.doc.value.name"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-briefcase size-5" />
			</span>
		</template>
		<template #status><span /></template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">The designation is named after its title. To rename it later, use Desk.</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value && can('Employee').read" #aside>
			<SummaryCard
				title="Usage"
				:items="[
					{
						label: 'Active employees',
						value: String(employees),
						route: `/employees?designation=${encodeURIComponent(page.doc.value.name)}&status=Active`,
					},
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

const props = defineProps<{ name: string | null }>()
const employees = ref(0)

const page = useDocPage("Designation", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew || !can("Employee").read) return
		employees.value = await getCount("Employee", [["designation", "=", doc.name], ["status", "=", "Active"]], [], true).catch(
			() => 0
		)
	},
})
</script>
