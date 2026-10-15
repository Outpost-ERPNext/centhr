<template>
	<div class="flex shrink-0 items-center gap-2">
		<template v-if="page.editing.value">
			<Button label="Discard" :disabled="!!page.busy.value" @click="page.discard" />
			<Button
				variant="solid"
				label="Save"
				:loading="page.busy.value === 'save'"
				:disabled="!page.isNew && !page.dirty.value"
				@click="page.save"
			/>
		</template>
		<template v-else-if="!page.loading.value && !page.notFound.value">
			<slot />
			<template v-if="page.canEdit.value">
				<Button icon-left="lucide-pencil" label="Edit" class="hidden sm:inline-flex" @click="page.startEdit" />
				<Button icon="lucide-pencil" aria-label="Edit" class="sm:hidden" @click="page.startEdit" />
			</template>
			<Button
				v-if="showSubmit"
				variant="solid"
				:label="submitLabel"
				:loading="page.busy.value === 'submit'"
				@click="page.submit()"
			/>
			<Dropdown v-if="moreOptions.length" :options="moreOptions" align="end">
				<Button icon="lucide-ellipsis" aria-label="More actions" />
			</Dropdown>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { Button, Dropdown } from "frappe-ui"
import type { useDocPage } from "@/data/useDocPage"

const props = withDefaults(
	defineProps<{
		page: ReturnType<typeof useDocPage>
		submitLabel?: string
		/** Set false when the page shows its own submit flow (for example approvals). */
		allowSubmit?: boolean
	}>(),
	{ submitLabel: "Submit", allowSubmit: true }
)

const showSubmit = computed(
	() =>
		props.allowSubmit &&
		props.page.isSubmittable.value &&
		props.page.docstatus.value === 0 &&
		props.page.permissions.value.submit
)

const moreOptions = computed(() => {
	const options = []
	if (props.page.docstatus.value === 1 && props.page.permissions.value.cancel) {
		options.push({ label: "Cancel", icon: "lucide-ban", onClick: props.page.cancel })
	}
	if (props.page.docstatus.value !== 1 && props.page.permissions.value.delete) {
		options.push({ label: "Delete", icon: "lucide-trash-2", theme: "red", onClick: props.page.remove })
	}
	return options
})
</script>
