<template>
	<DocPageShell
		doctype="PMS Questionnaire"
		list-label="Form Dashboard"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : `${page.doc.value.quarter} ${page.doc.value.fiscal_year}`"
		:read-only-fields="closed ? ['pms_questionnaire_list'] : []"
		:link-filters="linkFilters"
	>
		<template #actions>
			<DocActions :page="page">
				<template v-if="!page.isNew && page.canEdit.value">
					<Button v-if="closed" icon-left="lucide-undo-2" label="Reopen" :loading="busy" @click="reopen" />
					<Button v-else variant="solid" icon-left="lucide-send" label="Close and send" :loading="busy" @click="confirmClose" />
				</template>
			</DocActions>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill :tone="closed ? 'green' : 'amber'" :status="closed ? 'Closed and sent' : 'Open'" />
		</template>
		<template v-if="closed" #notice>
			<p class="rounded-4 bg-ch-subtle px-3 py-2 text-[13px] text-ch-ink-2">
				This questionnaire is closed and its reviewers have been asked. Reopen it to change the questions; that is possible until the
				first review is submitted.
			</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, dialog, toast } from "frappe-ui"
import DocActions from "@/components/DocActions.vue"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { closeQuestionnaires, reopenQuestionnaire } from "@/data/pmsReview"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Questionnaire", props.name)

const closed = computed(() => page.doc.value.status === "Completed")
const busy = ref(false)
const linkFilters = { employee: () => ({ status: "Active" }) }

function confirmClose() {
	dialog.confirm({
		title: "Close and send",
		message: "Close this questionnaire? The employee's line manager and peers are then asked for their review.",
		confirmLabel: "Close and send",
		onConfirm: close,
	})
}

async function close() {
	busy.value = true
	try {
		const outcome = await closeQuestionnaires([page.doc.value.name])
		if (outcome.failed.length) toast.error(outcome.failed[0].error)
		else toast.success("Questionnaire closed and reviewers asked")
		await page.reload()
	} finally {
		busy.value = false
	}
}

async function reopen() {
	busy.value = true
	try {
		await reopenQuestionnaire(page.doc.value.name)
		toast.success("Questionnaire reopened")
		await page.reload()
	} finally {
		busy.value = false
	}
}
</script>
