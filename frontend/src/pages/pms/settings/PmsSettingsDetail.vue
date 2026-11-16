<template>
	<DocPageShell
		doctype="PMS Settings"
		list-label="PMS Settings"
		:page="page"
		:title="page.doc.value.company || page.doc.value.name"
		:read-only-fields="page.isNew ? [] : ['company']"
	>
		<template #status><span /></template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Each company has one PMS policy. The two weights must add up to 100. A score range is written as 80-100, or &gt;100 for anything above.
			</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Settings", props.name)
</script>
