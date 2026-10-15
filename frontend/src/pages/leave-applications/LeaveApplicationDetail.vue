<template>
	<DocPageShell
		doctype="Leave Application"
		list-label="Leave Application"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="hiddenFields"
		:link-filters="linkFilters"
		@change="onChange"
	>
		<template #actions>
			<DocActions :page="page" :allow-submit="false">
				<Button
					v-if="employeeRoute"
					icon-left="lucide-user"
					label="View employee"
					class="hidden sm:inline-flex"
					:route="employeeRoute"
				/>
				<template v-if="workflow">
					<Button
						v-for="t in transitions"
						:key="t.action"
						:variant="isPositive(t.action) ? 'solid' : 'subtle'"
						:theme="isNegative(t.action) ? 'red' : 'gray'"
						:label="t.action"
						:loading="acting === t.action"
						@click="runTransition(t.action)"
					/>
				</template>
				<template v-else-if="canDecide">
					<Button theme="red" label="Reject" :loading="acting === 'Rejected'" @click="decide('Rejected')" />
					<Button variant="solid" label="Approve" :loading="acting === 'Approved'" @click="decide('Approved')" />
				</template>
				<Button
					v-else-if="canSubmitDecision"
					variant="solid"
					label="Submit"
					:loading="page.busy.value === 'submit'"
					@click="page.submit(`Submit this application as ${page.doc.value.status}?`)"
				/>
			</DocActions>
		</template>

		<template #status>
			<StatusBadge
				v-if="!page.isNew"
				pill
				doctype="Leave Application"
				:status="workflowState || page.doc.value.status"
			/>
		</template>

		<template #notice>
			<div
				v-if="page.editing.value && page.doc.value.employee && page.doc.value.leave_type"
				class="flex flex-wrap gap-x-6 gap-y-1 rounded-5 border border-ch-line bg-ch-surface px-4 py-3 text-[13px]"
			>
				<span class="text-ch-ink-3">
					Leave days <span class="font-medium tabular-nums text-ch-ink">{{ formatNumber(page.doc.value.total_leave_days) }}</span>
				</span>
				<span class="text-ch-ink-3">
					Balance before application
					<span class="font-medium tabular-nums text-ch-ink">{{ formatNumber(page.doc.value.leave_balance) }}</span>
				</span>
			</div>
		</template>

		<template v-if="!page.isNew && !page.editing.value" #aside>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-4 text-[14px] font-medium text-ch-ink">Approval</h3>
				<ol class="flex flex-col">
					<li v-for="(step, index) in steps" :key="index" class="relative flex gap-3 pb-5 last:pb-0">
						<span
							v-if="index < steps.length - 1"
							class="absolute left-[11px] top-6 h-[calc(100%-20px)] w-px bg-ch-line"
							aria-hidden="true"
						/>
						<span
							class="z-[1] flex size-6 shrink-0 items-center justify-center rounded-full"
							:style="{ background: STEP_STYLE[step.state].bg, color: STEP_STYLE[step.state].fg }"
						>
							<span v-if="STEP_STYLE[step.state].icon" class="size-3.5" :class="STEP_STYLE[step.state].icon" />
						</span>
						<div class="min-w-0 pt-0.5">
							<div class="text-[13.5px] font-medium" :class="step.state === 'todo' ? 'text-ch-ink-3' : 'text-ch-ink'">
								{{ step.label }}
							</div>
							<div class="truncate text-[12.5px] text-ch-ink-3">{{ step.sub }}</div>
						</div>
					</li>
				</ol>
				<p class="mt-4 rounded-4 bg-ch-subtle px-3 py-2 text-[12.5px] text-ch-ink-2">{{ note }}</p>
			</section>
			<SummaryCard
				title="Leave"
				:items="[
					{ label: 'Leave type', value: page.doc.value.leave_type },
					{ label: 'From', value: formatDate(page.doc.value.from_date) },
					{ label: 'To', value: formatDate(page.doc.value.to_date) },
					{ label: 'Days', value: formatNumber(page.doc.value.total_leave_days) },
					{ label: 'Balance before', value: formatNumber(page.doc.value.leave_balance) },
					{ label: 'Company', value: page.doc.value.company },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute } from "vue-router"
import { Button, dialog, toast } from "frappe-ui"
import DocPageShell from "@/components/DocPageShell.vue"
import DocActions from "@/components/DocActions.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { api } from "@/data/api"
import { submitDoc } from "@/data/doc"
import { session } from "@/data/session"
import { applyWorkflow, getTransitions, getWorkflow, type Workflow, type WorkflowTransition } from "@/data/workflow"
import { formatDate, formatDateShort, formatNumber } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()

const LA = "hrms.hr.doctype.leave_application.leave_application"

const workflow = ref<Workflow | null>(null)
const transitions = ref<WorkflowTransition[]>([])
const acting = ref<string | null>(null)

const page = useDocPage("Leave Application", props.name, {
	defaults: () => (route.query.employee ? { employee: route.query.employee } : {}),
	onLoaded: async (doc) => {
		workflow.value = await getWorkflow("Leave Application").catch(() => null)
		transitions.value = workflow.value && doc.name && !page.isNew ? await getTransitions(doc).catch(() => []) : []
		if (page.isNew && doc.employee) onChange("employee", doc.employee)
	},
})

// Filled in by the server, so they are not part of the form
const hiddenFields = ["naming_series", "salary_slip", "letter_head", "color", "amended_from"]

const linkFilters = {
	employee: () => ({ status: "Active" }),
}

const subtitle = computed(() => {
	const d = page.doc.value
	if (page.isNew || !d.from_date) return ""
	return `${d.leave_type} · ${formatDateShort(d.from_date)} – ${formatDateShort(d.to_date)} · ${formatNumber(d.total_leave_days)} days`
})

const employeeRoute = computed(() => (page.isNew ? null : routeFor("Employee", page.doc.value.employee)))
const workflowState = computed(() =>
	workflow.value ? page.doc.value[workflow.value.workflow_state_field] : null
)

const canDecide = computed(
	() =>
		!workflow.value &&
		page.docstatus.value === 0 &&
		page.doc.value.status === "Open" &&
		page.permissions.value.submit &&
		!page.editing.value
)
const canSubmitDecision = computed(
	() =>
		!workflow.value &&
		page.docstatus.value === 0 &&
		["Approved", "Rejected"].includes(page.doc.value.status) &&
		page.permissions.value.submit
)

const isPositive = (action: string) => /approv|accept|submit/i.test(action)
const isNegative = (action: string) => /reject|cancel|declin/i.test(action)

/** Without a workflow, HRMS approves or rejects by setting the status and submitting. */
function decide(status: "Approved" | "Rejected") {
	const doc = page.doc.value
	dialog.confirm({
		title: status === "Approved" ? "Approve leave" : "Reject leave",
		message:
			status === "Approved"
				? `Approve ${formatNumber(doc.total_leave_days)} days of ${doc.leave_type} for ${doc.employee_name}? The days are deducted from the leave balance and attendance is marked.`
				: `Reject this ${doc.leave_type} application from ${doc.employee_name}?`,
		confirmLabel: status === "Approved" ? "Approve" : "Reject",
		theme: status === "Approved" ? undefined : "red",
		onConfirm: async () => {
			acting.value = status
			try {
				await submitDoc({ ...doc, status })
				toast.success(`Leave application ${status.toLowerCase()}`)
				await page.reload()
			} finally {
				acting.value = null
			}
		},
	})
}

async function runTransition(action: string) {
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

let recalcTimer: ReturnType<typeof setTimeout> | undefined

/** Mirrors the Desk form: approver on employee change, days and balance on date changes. */
async function onChange(fieldname: string, value: any) {
	const doc = page.doc.value
	if (fieldname === "employee") {
		if (value) {
			const details = await api<{ leave_approver?: string; leave_approver_name?: string }>(
				"hrms.api.get_leave_approval_details",
				{ employee: value },
				{ silent: true }
			).catch(() => null)
			if (details?.leave_approver) {
				doc.leave_approver = details.leave_approver
				doc.leave_approver_name = details.leave_approver_name
			}
		}
	}
	if (fieldname === "half_day" && !value) doc.half_day_date = null
	if (fieldname === "from_date" && value && (!doc.to_date || doc.to_date < value)) doc.to_date = value
	if (["employee", "leave_type", "from_date", "to_date", "half_day", "half_day_date"].includes(fieldname)) {
		clearTimeout(recalcTimer)
		recalcTimer = setTimeout(recalculate, 200)
	}
}

async function recalculate() {
	const doc = page.doc.value
	if (!doc.employee || !doc.leave_type || !doc.from_date || !doc.to_date) return
	const [days, balance] = await Promise.all([
		api<number>(
			`${LA}.get_number_of_leave_days`,
			{
				employee: doc.employee,
				leave_type: doc.leave_type,
				from_date: doc.from_date,
				to_date: doc.to_date,
				half_day: doc.half_day,
				half_day_date: doc.half_day_date,
				leave_application: page.isNew ? undefined : doc.name,
			},
			{ silent: true }
		).catch(() => null),
		api<number>(
			`${LA}.get_leave_balance_on`,
			{
				employee: doc.employee,
				leave_type: doc.leave_type,
				date: doc.from_date,
				to_date: doc.to_date,
				consider_all_leaves_in_the_allocation_period: 1,
				leave_application: page.isNew ? undefined : doc.name,
			},
			{ silent: true }
		).catch(() => null),
	])
	if (days !== null) doc.total_leave_days = days
	if (balance !== null) doc.leave_balance = balance
}

type StepState = "done" | "current" | "rejected" | "todo"
const STEP_STYLE: Record<StepState, { bg: string; fg: string; icon: string }> = {
	done: { bg: "var(--ch-green-dot)", fg: "#fff", icon: "lucide-check" },
	current: { bg: "var(--ch-amber-dot)", fg: "#fff", icon: "lucide-clock" },
	rejected: { bg: "var(--ch-red-dot)", fg: "#fff", icon: "lucide-x" },
	todo: { bg: "var(--ch-subtle-2)", fg: "var(--ch-ink-3)", icon: "" },
}

const steps = computed<{ label: string; sub: string; state: StepState }[]>(() => {
	const d = page.doc.value
	if (workflow.value) {
		const current = workflowState.value
		const states = workflow.value.states.map((s) => s.state)
		const currentIndex = states.indexOf(current)
		return states.map((state, index) => ({
			label: state,
			sub: index === currentIndex ? "Current state" : "",
			state: index < currentIndex ? "done" : index === currentIndex ? (isNegative(state) ? "rejected" : d.docstatus === 1 ? "done" : "current") : "todo",
		}))
	}
	const rejected = d.status === "Rejected"
	const cancelled = d.docstatus === 2 || d.status === "Cancelled"
	const decided = d.status !== "Open"
	return [
		{ label: "Applied", sub: `${d.employee_name} · ${formatDate(d.posting_date)}`, state: "done" },
		{
			label: "Leave approver review",
			sub: d.leave_approver_name || d.leave_approver || "No approver set",
			state: rejected ? "rejected" : decided ? "done" : "current",
		},
		{
			label: cancelled ? "Cancelled" : rejected ? "Rejected" : d.docstatus === 1 ? "Approved" : "Decision",
			sub: d.docstatus === 1 || cancelled ? formatDate(d.modified?.slice(0, 10)) : "Awaiting decision",
			state: cancelled ? "rejected" : rejected ? "rejected" : d.docstatus === 1 ? "done" : "todo",
		},
	]
})

const note = computed(() => {
	const d = page.doc.value
	if (d.docstatus === 2) return "This application was cancelled. Its leave days are back in the balance."
	if (d.docstatus === 1) {
		return d.status === "Approved"
			? "Approved and submitted. The days are deducted from the leave balance and attendance is marked as On Leave."
			: "Rejected and submitted. No leave was deducted."
	}
	if (d.status !== "Open") return `Saved as ${d.status}. Submit it to make the decision final.`
	if (d.leave_approver === session.user) return "You are the leave approver for this application."
	return "Waiting for the leave approver. Approving deducts the days from the employee's leave balance."
})
</script>
