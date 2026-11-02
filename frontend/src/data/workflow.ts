import { computed, ref } from "vue"
import { toast } from "frappe-ui"
import { api } from "./api"
import type { useDocPage } from "./useDocPage"

export interface WorkflowTransition {
	action: string
	next_state: string
	allowed: string
	state: string
}

export interface Workflow {
	name: string
	workflow_state_field: string
	states: { state: string; doc_status: string; style?: string }[]
	transitions: WorkflowTransition[]
}

const cache: Record<string, Promise<Workflow | null>> = {}

/** The active Workflow for a DocType, or null when there is none. */
export function getWorkflow(doctype: string): Promise<Workflow | null> {
	if (!cache[doctype]) {
		cache[doctype] = api<Workflow | Record<string, never>>("hrms.api.get_workflow", { doctype }).then((wf) =>
			wf && (wf as Workflow).name ? (wf as Workflow) : null
		)
	}
	return cache[doctype]
}

/** Transitions the session user can apply to this document now. */
export function getTransitions(doc: Record<string, any>) {
	return api<WorkflowTransition[]>("frappe.model.workflow.get_transitions", { doc })
}

export function applyWorkflow(doc: Record<string, any>, action: string) {
	return api<Record<string, any>>("frappe.model.workflow.apply_workflow", { doc, action })
}

export const isPositiveAction = (action: string) => /approv|accept|submit/i.test(action)
export const isNegativeAction = (action: string) => /reject|cancel|declin/i.test(action)

/**
 * The active workflow of a document page and the actions the session user may take now.
 * Call `load` from the page's onLoaded, since transitions depend on the saved document.
 */
export function useWorkflowActions(doctype: string, page: ReturnType<typeof useDocPage>) {
	const workflow = ref<Workflow | null>(null)
	const transitions = ref<WorkflowTransition[]>([])
	const acting = ref<string | null>(null)
	const state = computed(() => (workflow.value ? page.doc.value[workflow.value.workflow_state_field] : null))

	async function load(doc: Record<string, any>) {
		workflow.value = await getWorkflow(doctype).catch(() => null)
		transitions.value = workflow.value && doc.name && !page.isNew ? await getTransitions(doc).catch(() => []) : []
	}

	async function run(action: string) {
		acting.value = action
		try {
			await applyWorkflow(page.doc.value, action)
			toast.success(`${action} applied`)
			await page.reload()
		} catch {
			// Shown by the api helper
		} finally {
			acting.value = null
		}
	}

	return { workflow, transitions, acting, state, load, run }
}

export type WorkflowActions = ReturnType<typeof useWorkflowActions>
