<template>
	<DocPageShell doctype="KPI UOM" list-label="KPI UOM" :page="page" :title="page.doc.value.name">
		<template #status><span /></template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">The unit a KPI target is measured in, such as %, Count or Days. KPI Templates pick it for each KPI.</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import DocPageShell from "@/components/DocPageShell.vue"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("KPI UOM", props.name)
</script>
