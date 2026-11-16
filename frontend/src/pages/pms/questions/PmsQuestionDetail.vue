<template>
	<DocPageShell
		doctype="PMS Question"
		list-label="Question Bank"
		:page="page"
		:title="page.doc.value.question || page.doc.value.name"
		:hidden-fields="['naming_series']"
		:link-filters="linkFilters"
	>
		<template #status>
			<StatusBadge
				v-if="!page.isNew"
				pill
				:tone="page.doc.value.is_a_general_question ? 'blue' : 'gray'"
				:status="page.doc.value.is_a_general_question ? 'Everyone' : 'Department or designation'"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Question", props.name)

// A question is asked in a real department and an active designation
const linkFilters = {
	department: () => ({ is_group: 0 }),
	designation: () => ({ disabled: 0 }),
}
</script>
