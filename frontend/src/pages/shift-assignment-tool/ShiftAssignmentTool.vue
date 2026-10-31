<template>
	<PageHeader :crumbs="[{ label: 'Shift Assignment', route: '/shift-assignments' }, { label: 'Shift Assignment Tool' }]">
		<template v-if="ready" #actions>
			<Dropdown v-if="processing" :options="processOptions" align="end">
				<Button
					variant="solid"
					label="Process Requests"
					icon-right="lucide-chevron-down"
					:loading="!!busy"
					:disabled="!!busy"
				/>
			</Dropdown>
			<Button v-else variant="solid" :label="doc.action" :loading="!!busy" :disabled="!!busy" @click="confirmAssign" />
		</template>
	</PageHeader>

	<div class="min-h-0 flex-1 overflow-y-auto">
		<div v-if="!ready" class="px-5 py-16 text-center text-sm text-ch-ink-3">Loading…</div>
		<div v-else class="mx-auto flex w-full max-w-[1240px] flex-col gap-4 p-4 sm:p-5">
			<DocForm :doctype="DT" :doc="doc" :hidden-fields="['filter_list', 'employees_html']" @change="onChange" />

			<!-- The filter_list and employees_html sections of the Desk form -->
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5">
				<h3 class="mb-4 text-[14px] font-medium text-ch-ink">Advanced Filters</h3>
				<EmployeeFilterGroup v-model="advancedFilters" @update:model-value="scheduleLoad" />
			</section>

			<section class="flex flex-col gap-3 rounded-5 border border-ch-line bg-ch-surface py-4 sm:py-5">
				<div class="flex flex-wrap items-center gap-2 px-4 sm:px-5">
					<h3 class="text-[14px] font-medium text-ch-ink">
						{{ processing ? "Select Shift Requests" : "Select Employees" }}
					</h3>
					<span class="text-[13px] text-ch-ink-3">
						{{ shownRows.length }} {{ processing ? "shift requests" : "employees" }} · {{ selected.length }} selected
					</span>
					<Button
						v-if="selected.length"
						size="sm"
						variant="ghost"
						label="Clear selection"
						class="ml-auto"
						@click="selected = []"
					/>
				</div>
				<DataTable
					v-model:selected="selected"
					v-model:column-filters="columnFilters"
					:columns="columns"
					:rows="shownRows"
					:row-key="processing ? 'name' : 'employee'"
					:loading="loading"
					:clickable="false"
					selectable
					inline-filters
					:empty-message="emptyMessage"
					empty-icon="lucide-users"
					min-width="760px"
				>
					<template #cell-name="{ row }">
						<a
							:href="`/app/shift-request/${encodeURIComponent(row.name)}`"
							target="_blank"
							class="text-ch-ink underline-offset-2 hover:underline"
						>
							{{ row.name }}
						</a>
					</template>
				</DataTable>
			</section>
		</div>
	</div>

	<!-- hrms.notify_bulk_action_status -->
	<Dialog v-if="result" :open="!!result" :title="result.title" size="lg" @update:open="(v: boolean) => !v && (result = null)">
		<div class="flex flex-col gap-3 text-[13px] text-ch-ink">
			<template v-if="result.failed.length">
				<p>Failed to {{ result.processed ? "process" : "create/submit" }} {{ result.doctype }} for employees: {{ commaAnd(result.failed) }}</p>
				<p class="text-ch-ink-3">
					Check
					<a
						:href="`/app/error-log?reference_doctype=${encodeURIComponent(result.doctype)}`"
						target="_blank"
						class="text-ch-ink underline"
					>
						Error Log
					</a>
					for more details
				</p>
				<hr v-if="result.created.length" class="border-ch-line" />
			</template>
			<template v-if="result.created.length">
				<p>Successfully {{ result.processed ? "processed" : "created" }} {{ result.doctype }} for the following employees:</p>
				<div class="max-h-80 overflow-y-auto rounded-4 border border-ch-line">
					<table class="w-full text-left">
						<thead class="sticky top-0 bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-1.5 font-normal">Employee</th>
								<th class="px-3 py-1.5 font-normal">{{ result.doctype }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="d in result.created" :key="d.name" class="border-t border-ch-line">
								<td class="px-3 py-1.5">{{ d.employee }}<span v-if="d.employee_name" class="text-ch-ink-3"> · {{ d.employee_name }}</span></td>
								<td class="px-3 py-1.5">
									<RouterLink
										v-if="!result.processed"
										:to="`/shift-assignments/${encodeURIComponent(d.name)}`"
										class="underline-offset-2 hover:underline"
									>
										{{ d.name }}
									</RouterLink>
									<a
										v-else
										:href="`/app/shift-request/${encodeURIComponent(d.name)}`"
										target="_blank"
										class="underline-offset-2 hover:underline"
									>
										{{ d.name }}
									</a>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</template>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, Dropdown, dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import DocForm from "@/components/DocForm.vue"
import { api } from "@/data/api"
import { missingRequired, newDoc } from "@/data/doc"
import { loadMeta } from "@/data/meta"
import { formatDateShort } from "@/utils/format"
import EmployeeFilterGroup, { type EmployeeFilter } from "./EmployeeFilterGroup.vue"

const DT = "Shift Assignment Tool"
const API = "centhr.api.shift_assignment_tool"

type Created = { name: string; employee: string; employee_name?: string }
type RunResult = { queued: boolean; created?: Created[]; failed?: string[] }

interface Result {
	title: string
	doctype: string
	processed: boolean
	created: Created[]
	failed: string[]
}

const ready = ref(false)
const doc = ref<Record<string, any>>({})
const rows = ref<Record<string, any>[]>([])
const selected = ref<string[]>([])
const advancedFilters = ref<EmployeeFilter[]>([])
const columnFilters = ref<Record<string, string>>({})
const loading = ref(false)
const busy = ref(false)
const result = ref<Result | null>(null)

const processing = computed(() => doc.value.action === "Process Shift Requests")

Promise.all([loadMeta(DT), api<{ company: string | null }>(`${API}.get_defaults`, {}).catch(() => ({ company: null }))]).then(
	([, defaults]) => {
		doc.value = newDoc(DT, defaults.company ? { company: defaults.company } : {})
		ready.value = true
		loadRows()
	}
)

/** The tool lists nothing until the shift (or schedule) and the start date are picked, as in Desk. */
const canList = computed(() => {
	const d = doc.value
	if (d.action === "Assign Shift") return !!(d.shift_type && d.start_date)
	if (d.action === "Assign Shift Schedule") return !!(d.shift_schedule && d.start_date)
	return true
})

const emptyMessage = computed(() => {
	const d = doc.value
	if (d.action === "Assign Shift")
		return canList.value
			? "There are no employees without Shift Assignments for these dates based on the given filters."
			: "Please select Shift Type and assignment date(s)."
	if (d.action === "Assign Shift Schedule")
		return canList.value
			? "There are no employees without active overlapping Shift Schedule Assignments based on the given filters."
			: "Please select Shift Schedule and assignment date(s)."
	return "There are no open Shift Requests based on the given filters."
})

const date = (v: string) => (v ? formatDateShort(v) : "")
const columns = computed<Column[]>(() =>
	processing.value
		? [
				{ key: "name", label: "Shift Request", width: "minmax(150px,1fr)" },
				{ key: "employee_name", label: "Employee", width: "minmax(200px,2fr)" },
				{ key: "shift_type", label: "Shift Type", width: "minmax(120px,1fr)" },
				{ key: "from_date", label: "From Date", width: "110px", format: date },
				{ key: "to_date", label: "To Date", width: "110px", format: date },
			]
		: [
				{ key: "employee", label: "Employee", width: "minmax(130px,1fr)" },
				{ key: "employee_name", label: "Employee Name", width: "minmax(180px,2fr)" },
				{ key: "branch", label: "Branch", width: "minmax(110px,1fr)", hideOnMobile: true },
				{ key: "department", label: "Department", width: "minmax(130px,1fr)" },
				{ key: "default_shift", label: "Default Shift", width: "minmax(110px,1fr)" },
			]
)

/** The rows that match every column search box, on the shown text, like the inline filters of a Desk datatable. */
const shownRows = computed(() => {
	const active = columns.value.filter((c) => columnFilters.value[c.key]?.trim())
	if (!active.length) return rows.value
	return rows.value.filter((row) =>
		active.every((c) => {
			const text = c.format ? c.format(row[c.key], row) : String(row[c.key] ?? "")
			return text.toLowerCase().includes(columnFilters.value[c.key].trim().toLowerCase())
		})
	)
})

function onChange(fieldname: string) {
	const d = doc.value
	// The date rules of shift_assignment_tool.js
	if (fieldname === "start_date" && d.start_date && d.end_date && d.start_date > d.end_date) d.end_date = null
	if (fieldname === "end_date" && d.start_date && d.end_date && d.end_date < d.start_date) d.start_date = null
	if (fieldname === "from_date" && d.from_date && d.to_date && d.from_date > d.to_date) d.to_date = null
	if (fieldname === "to_date" && d.from_date && d.to_date && d.to_date < d.from_date) d.from_date = null
	if (fieldname === "action") {
		rows.value = []
		columnFilters.value = {}
	}
	scheduleLoad()
}

let timer: ReturnType<typeof setTimeout> | undefined
function scheduleLoad() {
	clearTimeout(timer)
	timer = setTimeout(loadRows, 300)
}

let requestId = 0
async function loadRows() {
	const id = ++requestId
	selected.value = []
	if (!canList.value) {
		rows.value = []
		loading.value = false
		return
	}
	loading.value = true
	try {
		const data = await api<Record<string, any>[]>(`${API}.get_employees`, {
			values: doc.value,
			advanced_filters: advancedFilters.value,
		})
		if (id === requestId) rows.value = data || []
	} catch {
		if (id === requestId) rows.value = []
	} finally {
		if (id === requestId) loading.value = false
	}
}

/** hrms.validate_mandatory_fields: required fields first, then at least one ticked row. */
function validate(items: string) {
	const missing = missingRequired(DT, doc.value)
	if (missing.length) {
		alert("Missing Fields", `Mandatory fields required for this action: ${missing.join(", ")}`)
		return false
	}
	if (!selected.value.length) {
		alert(`No ${items} Selected`, "Please select at least one row to perform this action.")
		return false
	}
	return true
}

function alert(title: string, message: string) {
	dialog.confirm({ title, message, theme: "red", actions: [{ label: "OK", variant: "solid" }] })
}

function confirmAssign() {
	if (!validate("Employees")) return
	const action = doc.value.action
	const employees = [...selected.value]
	dialog.confirm({
		title: "Confirm",
		message: `${action} to ${employees.length} employee(s)?`,
		confirmLabel: "Yes",
		onConfirm: () => {
			run(action === "Assign Shift" ? "Shift Assignment" : "Shift Schedule Assignment", false, () =>
				api<RunResult>(`${API}.bulk_assign`, { values: doc.value, employees })
			)
		},
	})
}

const processOptions = computed(() => [
	{ label: "Approve", icon: "lucide-check", onClick: () => confirmProcess("Approved") },
	{ label: "Reject", icon: "lucide-x", onClick: () => confirmProcess("Rejected") },
])

function confirmProcess(status: "Approved" | "Rejected") {
	if (!validate("Shift Requests")) return
	const requests = rows.value
		.filter((r) => selected.value.includes(r.name))
		.map((r) => ({ shift_request: r.name, employee: r.employee }))
	dialog.confirm({
		title: "Confirm",
		message: `Process ${requests.length} Shift Request(s) as ${status}?`,
		confirmLabel: "Yes",
		onConfirm: () => {
			run("Shift Request", true, () =>
				api<RunResult>(`${API}.process_shift_requests`, { values: doc.value, shift_requests: requests, status })
			)
		},
	})
}

async function run(doctype: string, processed: boolean, call: () => Promise<RunResult>) {
	busy.value = true
	try {
		const res = await call()
		if (res.queued) {
			toast.info(
				processed
					? "Processing of Shift Requests has been queued. It may take a few minutes."
					: `Creation of ${doctype}s has been queued. It may take a few minutes.`
			)
			return
		}
		const created = res.created || []
		const failed = res.failed || []
		const title = failed.length ? (created.length ? "Partial Success" : "Failure") : "Success"
		result.value = { title, doctype, processed, created, failed }
		// frm.refresh() in Desk: the list loads again without the rows just handled
		if (created.length) await loadRows()
	} catch {
		// The api helper already showed the server's message
	} finally {
		busy.value = false
	}
}

/** frappe.utils.comma_and */
function commaAnd(items: string[]) {
	return items.length > 1 ? `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}` : items.join("")
}
</script>
