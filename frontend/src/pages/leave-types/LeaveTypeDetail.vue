<template>
	<DocPageShell
		doctype="Leave Type"
		list-label="Leave Type"
		:page="page"
		:title="page.doc.value.leave_type_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : leaveTypeRules(page.doc.value)"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-calendar-days size-5" />
			</span>
		</template>
		<template #status><span /></template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Usage"
				:items="[
					{ label: 'Submitted allocations', value: counts.allocations, route: `/leave-allocations?leave_type=${encodeURIComponent(page.doc.value.name)}&state=1` },
					{ label: 'Days allocated', value: formatNumber(counts.allocated) },
					{ label: 'Applications', value: counts.applications, route: `/leave-applications?leave_type=${encodeURIComponent(page.doc.value.name)}` },
					{ label: 'Open applications', value: counts.open, route: `/leave-applications?leave_type=${encodeURIComponent(page.doc.value.name)}&status=Open` },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { reactive } from "vue"
import DocPageShell from "@/components/DocPageShell.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { getCount, getList } from "@/data/list"
import { formatNumber } from "@/utils/format"
import { leaveTypeRules } from "./rules"

const props = defineProps<{ name: string | null }>()
const counts = reactive({ allocations: 0, allocated: 0, applications: 0, open: 0 })

const page = useDocPage("Leave Type", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew) return
		const lt = [["leave_type", "=", doc.name]] as [string, string, any][]
		const [alloc, apps, open] = await Promise.all([
			getList<{ count: number; total: number }>({
				doctype: "Leave Allocation",
				fields: [{ COUNT: "*", as: "count" }, { SUM: "total_leaves_allocated", as: "total" }],
				filters: [...lt, ["docstatus", "=", 1]],
				limit: 1,
				silent: true,
			}).catch(() => []),
			getCount("Leave Application", [...lt, ["docstatus", "<", 2]], [], true).catch(() => 0),
			getCount("Leave Application", [...lt, ["status", "=", "Open"], ["docstatus", "=", 0]], [], true).catch(() => 0),
		])
		counts.allocations = alloc[0]?.count || 0
		counts.allocated = alloc[0]?.total || 0
		counts.applications = apps
		counts.open = open
	},
})
</script>
