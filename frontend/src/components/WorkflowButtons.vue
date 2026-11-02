<template>
	<Button
		v-for="t in actions.transitions.value"
		:key="t.action"
		:variant="isPositiveAction(t.action) ? 'solid' : 'subtle'"
		:theme="isNegativeAction(t.action) ? 'red' : 'gray'"
		:label="t.action"
		:loading="actions.acting.value === t.action"
		:disabled="!!actions.acting.value && actions.acting.value !== t.action"
		@click="actions.run(t.action)"
	/>
</template>

<script setup lang="ts">
import { Button } from "frappe-ui"
import { isNegativeAction, isPositiveAction, type WorkflowActions } from "@/data/workflow"

/** The workflow actions the session user may take on the document, as buttons. */
defineProps<{ actions: WorkflowActions }>()
</script>
