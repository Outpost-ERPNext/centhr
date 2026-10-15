import { api } from "./api"

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
