<template>
	<DocPageShell
		doctype="Channel"
		list-label="Channel"
		:page="page"
		:title="page.doc.value.channel || page.doc.value.name"
		:link-filters="linkFilters"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-radio-tower size-5" />
			</span>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew && page.doc.value.disabled" pill status="Disabled" tone="gray" />
			<span v-else />
		</template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">The channel is named after its title. To rename it later, use Desk.</p>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Income account', value: page.doc.value.income_account },
					{ label: 'Expense account', value: page.doc.value.expense_account },
					{ label: 'Payment approval', value: page.doc.value.enable_payment_approval ? 'Enabled' : 'Disabled' },
					...(can('Employee').read
						? [
								{
									label: 'Active employees',
									value: String(employees),
									route: `/employees?channel=${encodeURIComponent(page.doc.value.name)}&status=Active`,
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
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getCount } from "@/data/list"
import { can } from "@/data/permissions"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const employees = ref(0)

const page = useDocPage("Channel", props.name, {
	onLoaded: async (doc) => {
		if (page.isNew || !can("Employee").read) return
		employees.value = await getCount("Employee", [["channel", "=", doc.name], ["status", "=", "Active"]], [], true).catch(
			() => 0
		)
	},
})

// Posting accounts must be ledgers, as in Desk
const linkFilters = { income_account: () => ({ is_group: 0 }), expense_account: () => ({ is_group: 0 }) }
</script>
