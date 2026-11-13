<template>
	<DocPageShell
		doctype="Cost Center"
		list-label="Cost Center"
		:page="page"
		:title="page.doc.value.cost_center_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : page.doc.value.company || ''"
		:hidden-fields="['lft', 'rgt', 'old_parent']"
		:link-filters="linkFilters"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span :class="page.doc.value.is_group ? 'lucide-folder-tree' : 'lucide-landmark'" class="size-5" />
			</span>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew && page.doc.value.disabled" pill status="Disabled" tone="gray" />
			<span v-else />
		</template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Cost centers form a tree for each company. Only a group can be a parent, and the cost center is named with the
				company's abbreviation.
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Company', value: page.doc.value.company },
					{
						label: 'Parent',
						value: page.doc.value.parent_cost_center,
						route: routeFor('Cost Center', page.doc.value.parent_cost_center),
					},
					{ label: 'Type', value: page.doc.value.is_group ? 'Group' : 'Cost center' },
					...(page.doc.value.is_group
						? [
								{
									label: 'Child cost centers',
									value: String(counts.children),
									route: `/cost-centers?parent_cost_center=${encodeURIComponent(page.doc.value.name)}`,
								},
							]
						: []),
					...(can('Employee').read
						? [
								{
									label: 'Active employees',
									value: String(counts.employees),
									route: `/employees?cost_center=${encodeURIComponent(page.doc.value.name)}&status=Active`,
								},
							]
						: []),
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { reactive } from "vue"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getCount } from "@/data/list"
import { can } from "@/data/permissions"
import { useDocPage } from "@/data/useDocPage"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const counts = reactive({ employees: 0, children: 0 })

const page = useDocPage("Cost Center", props.name, {
	defaults: () => (route.query.company ? { company: route.query.company } : {}),
	onLoaded: async (doc) => {
		if (page.isNew) return
		const [employees, children] = await Promise.all([
			can("Employee").read
				? getCount("Employee", [["cost_center", "=", doc.name], ["status", "=", "Active"]], [], true).catch(() => 0)
				: 0,
			doc.is_group ? getCount("Cost Center", [["parent_cost_center", "=", doc.name]], [], true).catch(() => 0) : 0,
		])
		counts.employees = employees
		counts.children = children
	},
})

// As in the ERPNext Cost Center form: the parent is a group of the same company
const linkFilters = {
	parent_cost_center: (doc: Record<string, any>) => ({ is_group: 1, ...(doc.company ? { company: doc.company } : {}) }),
}
</script>
