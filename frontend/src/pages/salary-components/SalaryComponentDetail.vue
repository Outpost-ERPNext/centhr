<template>
	<DocPageShell
		doctype="Salary Component"
		list-label="Salary Component"
		:page="page"
		:title="page.doc.value.salary_component || page.doc.value.name"
		:subtitle="page.isNew ? '' : [page.doc.value.type, page.doc.value.salary_component_abbr].filter(Boolean).join(' · ')"
	>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill :tone="page.doc.value.disabled ? 'gray' : 'green'" :status="page.doc.value.disabled ? 'Disabled' : 'Enabled'" />
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("Salary Component", props.name)
</script>
