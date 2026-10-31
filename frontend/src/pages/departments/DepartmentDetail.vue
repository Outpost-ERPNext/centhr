<template>
	<DocPageShell
		doctype="Department"
		list-label="Department"
		:page="page"
		:title="page.doc.value.department_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : page.doc.value.company || 'All companies'"
		:hidden-fields="['lft', 'rgt', 'old_parent']"
		:link-filters="linkFilters"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span :class="page.doc.value.is_group ? 'lucide-folder-tree' : 'lucide-building-2'" class="size-5" />
			</span>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew && page.doc.value.disabled" pill status="Disabled" tone="gray" />
			<span v-else />
		</template>
		<template v-if="!page.isNew && !page.doc.value.parent_department" #notice>
			<p class="rounded-5 border border-ch-line bg-ch-subtle px-4 py-3 text-[13px] text-ch-ink-2">
				This is the root department. It cannot be edited.
			</p>
		</template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Departments form a tree. Only a group can be a parent, and a department with a company is named with the
				company's abbreviation.
			</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Company', value: page.doc.value.company || 'All companies' },
					{
						label: 'Parent',
						value: page.doc.value.parent_department,
						route: routeFor('Department', page.doc.value.parent_department),
					},
					{ label: 'Type', value: page.doc.value.is_group ? 'Group' : 'Department' },
					...(page.doc.value.is_group
						? [
								{
									label: 'Sub-departments',
									value: String(counts.children),
									route: `/departments?parent_department=${encodeURIComponent(page.doc.value.name)}`,
								},
							]
						: []),
					...(can('Employee').read
						? [
								{
									label: 'Active employees',
									value: String(counts.employees),
									route: `/employees?department=${encodeURIComponent(page.doc.value.name)}&status=Active`,
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

const page = useDocPage("Department", props.name, {
	defaults: () => (route.query.company ? { company: route.query.company } : {}),
	onLoaded: async (doc) => {
		if (page.isNew) return
		const [employees, children] = await Promise.all([
			can("Employee").read
				? getCount("Employee", [["department", "=", doc.name], ["status", "=", "Active"]], [], true).catch(() => 0)
				: 0,
			doc.is_group ? getCount("Department", [["parent_department", "=", doc.name]], [], true).catch(() => 0) : 0,
		])
		counts.employees = employees
		counts.children = children
	},
})

// As in the ERPNext Department form
const linkFilters = { parent_department: () => ({ is_group: 1 }) }
</script>
