<template>
	<DocPageShell
		doctype="PMS 360 Degree"
		list-label="Weight & 360° Assignment"
		:page="page"
		:title="page.isNew ? '' : `${page.doc.value.quarter} ${page.doc.value.fiscal_year}`"
		:subtitle="page.doc.value.company"
		:read-only-fields="page.isNew ? [] : ['company', 'fiscal_year', 'quarter']"
		:link-filters="linkFilters"
	>
		<template #status><span /></template>
		<template v-if="page.editing.value" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				List the departments reviewed this quarter. Each line manager's review and each peer's review counts with the weight you give
				it, for example 60 and 40. Only employees of these departments get a questionnaire.
			</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS 360 Degree", props.name)

// A review is set up for the real departments of its company
const linkFilters = {
	"departments.department": (doc: Record<string, any>) => ({ is_group: 0, ...(doc.company ? { company: doc.company } : {}) }),
}
</script>
