<template>
	<DocPageShell doctype="PMS Question Trait" list-label="Question Trait" :page="page" :title="page.doc.value.name">
		<template #status><span /></template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">The quality a review question measures, such as Teamwork or Ownership.</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Question Trait", props.name)
</script>
