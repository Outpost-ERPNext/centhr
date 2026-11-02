<template>
	<PageHeader
		:crumbs="[
			{ label: 'Salary Structure Assignment', route: '/salary-structure-assignments' },
			{ label: 'Bulk Assign' },
		]"
	>
		<template v-if="ready" #actions>
			<Dropdown v-if="selected.length" :options="updateOptions" align="end">
				<Button label="Update" icon-right="lucide-chevron-down" />
			</Dropdown>
			<Button variant="solid" label="Assign Structure" :loading="busy" :disabled="busy" @click="confirmAssign" />
		</template>
	</PageHeader>

	<div class="min-h-0 flex-1 overflow-y-auto">
		<div v-if="!ready" class="px-5 py-16 text-center text-sm text-ch-ink-3">Loading…</div>
		<div v-else class="mx-auto flex w-full max-w-[1240px] flex-col gap-4 p-4 sm:p-5">
			<DocForm
				:doctype="DT"
				:doc="doc"
				:hidden-fields="['filter_list', 'employees_html']"
				:link-filters="linkFilters"
				@change="onChange"
			/>

			<!-- The filter_list and employees_html sections of the Desk form -->
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5">
				<h3 class="mb-4 text-[14px] font-medium text-ch-ink">Advanced Filters</h3>
				<EmployeeFilterGroup v-model="advancedFilters" @update:model-value="scheduleLoad" />
			</section>

			<section class="flex flex-col gap-3 rounded-5 border border-ch-line bg-ch-surface py-4 sm:py-5">
				<div class="flex flex-wrap items-center gap-2 px-4 sm:px-5">
					<h3 class="text-[14px] font-medium text-ch-ink">Select Employees</h3>
					<span class="text-[13px] text-ch-ink-3">{{ shownRows.length }} employees · {{ selected.length }} selected</span>
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
					row-key="employee"
					:loading="loading"
					:clickable="false"
					selectable
					inline-filters
					:empty-message="emptyMessage"
					empty-icon="lucide-users"
					mobile-aside="base"
					min-width="760px"
				>
					<template #cell-base="{ row }">
						<input
							v-model.number="row.base"
							type="number"
							min="0"
							class="h-7 w-full rounded-4 border border-ch-line bg-ch-surface px-2 text-[13px] tabular-nums text-ch-ink"
							:aria-label="`Base for ${row.employee_name}`"
						/>
					</template>
					<template #cell-variable="{ row }">
						<input
							v-model.number="row.variable"
							type="number"
							min="0"
							class="h-7 w-full rounded-4 border border-ch-line bg-ch-surface px-2 text-[13px] tabular-nums text-ch-ink"
							:aria-label="`Variable for ${row.employee_name}`"
						/>
					</template>
				</DataTable>
			</section>
		</div>
	</div>

	<!-- render_update_button in the Desk form -->
	<Dialog v-model:open="updateOpen" :title="`Set ${updateField} for selected employees`" size="sm">
		<input
			v-model.number="updateValue"
			type="number"
			min="0"
			class="h-8 w-full rounded-4 border border-ch-line bg-ch-surface px-2 text-[13px] tabular-nums text-ch-ink"
			:aria-label="updateField"
		/>
		<template #actions>
			<div class="flex justify-end">
				<Button variant="solid" label="Update" @click="applyUpdate" />
			</div>
		</template>
	</Dialog>

	<!-- hrms.notify_bulk_action_status -->
	<Dialog v-if="result" :open="!!result" :title="result.title" size="lg" @update:open="(v: boolean) => !v && (result = null)">
		<div class="flex flex-col gap-3 text-[13px] text-ch-ink">
			<template v-if="result.failed.length">
				<p>Failed to create/submit {{ ASSIGNMENT }} for employees: {{ result.failed.join(", ") }}</p>
				<p class="text-ch-ink-3">
					Check
					<a
						:href="`/app/error-log?reference_doctype=${encodeURIComponent(ASSIGNMENT)}`"
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
				<p>Successfully created {{ ASSIGNMENT }} for the following employees:</p>
				<div class="max-h-80 overflow-y-auto rounded-4 border border-ch-line">
					<table class="w-full text-left">
						<thead class="sticky top-0 bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-1.5 font-normal">Employee</th>
								<th class="px-3 py-1.5 font-normal">{{ ASSIGNMENT }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="d in result.created" :key="d.name" class="border-t border-ch-line">
								<td class="px-3 py-1.5">{{ d.employee }}<span v-if="d.employee_name" class="text-ch-ink-3"> · {{ d.employee_name }}</span></td>
								<td class="px-3 py-1.5">
									<RouterLink :to="`/salary-structure-assignments/${encodeURIComponent(d.name)}`" class="underline-offset-2 hover:underline">
										{{ d.name }}
									</RouterLink>
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
import { getList } from "@/data/list"
import { loadMeta } from "@/data/meta"
import EmployeeFilterGroup, { type EmployeeFilter } from "@/pages/shift-assignment-tool/EmployeeFilterGroup.vue"

const DT = "Bulk Salary Structure Assignment"
const ASSIGNMENT = "Salary Structure Assignment"
const API = "centhr.api.bulk_salary_structure_assignment"

type Created = { name: string; employee: string; employee_name?: string }
type RunResult = { queued: boolean; created?: Created[]; failed?: string[] }

const ready = ref(false)
const doc = ref<Record<string, any>>({})
const rows = ref<Record<string, any>[]>([])
const selected = ref<string[]>([])
const advancedFilters = ref<EmployeeFilter[]>([])
const columnFilters = ref<Record<string, string>>({})
const loading = ref(false)
const busy = ref(false)
const companyCurrency = ref<string | null>(null)
const result = ref<{ title: string; created: Created[]; failed: string[] } | null>(null)

loadMeta(DT).then(() => {
	doc.value = newDoc(DT)
	ready.value = true
})

// As in bulk_salary_structure_assignment.js
const linkFilters = {
	salary_structure: () => ({ docstatus: 1, is_active: "Yes" }),
	income_tax_slab: (d: Record<string, any>) => ({ company: d.company, disabled: 0, docstatus: 1, currency: d.currency }),
	payroll_payable_account: (d: Record<string, any>) => ({
		company: d.company,
		root_type: "Liability",
		is_group: 0,
		account_currency: ["in", [d.currency, companyCurrency.value]],
	}),
}

/** The structure sets the company, so the list waits for both; Desk lists employees of every company until then. */
const canList = computed(() => !!(doc.value.salary_structure && doc.value.company && doc.value.from_date))

const emptyMessage = computed(() =>
	canList.value
		? "There are no employees without a Salary Structure Assignment on this date based on the given filters."
		: "Please select Salary Structure and From Date."
)

const columns: Column[] = [
	{ key: "employee", label: "Employee", width: "minmax(130px,1fr)" },
	{ key: "employee_name", label: "Name", width: "minmax(180px,2fr)" },
	{ key: "grade", label: "Grade", width: "minmax(110px,1fr)", hideOnMobile: true },
	{ key: "base", label: "Base", width: "130px" },
	{ key: "variable", label: "Variable", width: "130px", hideOnMobile: true },
]

/** The rows that match every column search box, like the inline filters of a Desk datatable. */
const shownRows = computed(() => {
	const active = columns.filter((c) => columnFilters.value[c.key]?.trim())
	if (!active.length) return rows.value
	return rows.value.filter((row) =>
		active.every((c) =>
			String(row[c.key] ?? "")
				.toLowerCase()
				.includes(columnFilters.value[c.key].trim().toLowerCase())
		)
	)
})

async function onChange(fieldname: string) {
	if (fieldname === "salary_structure") await applyStructure()
	scheduleLoad()
}

let structureRequest = 0
/** fetch_from on the Desk form: the structure's company and currency, then the company's payable account. */
async function applyStructure() {
	const id = ++structureRequest
	const d = doc.value
	const [structure] = d.salary_structure
		? await getList<{ company: string; currency: string }>({
				doctype: "Salary Structure",
				fields: ["company", "currency"],
				filters: [["name", "=", d.salary_structure]],
				limit: 1,
			})
		: []
	const [company] = structure
		? await getList<{ default_payroll_payable_account: string | null; default_currency: string | null }>({
				doctype: "Company",
				fields: ["default_payroll_payable_account", "default_currency"],
				filters: [["name", "=", structure.company]],
				limit: 1,
			})
		: []
	if (id !== structureRequest) return
	d.company = structure?.company || null
	d.currency = structure?.currency || null
	d.income_tax_slab = null
	d.payroll_payable_account = company?.default_payroll_payable_account || null
	companyCurrency.value = company?.default_currency || null
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

const updateOpen = ref(false)
const updateField = ref<"Base" | "Variable">("Base")
const updateValue = ref<number | "">(0)
const updateOptions = (["Base", "Variable"] as const).map((label) => ({
	label,
	onClick: () => {
		updateField.value = label
		updateValue.value = 0
		updateOpen.value = true
	},
}))

function applyUpdate() {
	const key = updateField.value.toLowerCase()
	for (const row of rows.value) if (selected.value.includes(row.employee)) row[key] = Number(updateValue.value) || 0
	updateOpen.value = false
}

function alert(title: string, message: string) {
	dialog.confirm({ title, message, theme: "red", actions: [{ label: "OK", variant: "solid" }] })
}

function confirmAssign() {
	const missing = missingRequired(DT, doc.value)
	if (missing.length) return alert("Missing Fields", `Mandatory fields required for this action: ${missing.join(", ")}`)
	if (!selected.value.length) return alert("No Employees Selected", "Please select at least one row to perform this action.")

	const employees = rows.value
		.filter((r) => selected.value.includes(r.employee))
		.map((r) => ({ employee: r.employee, base: Number(r.base) || 0, variable: Number(r.variable) || 0 }))
	const noBase = employees.filter((e) => !e.base).map((e) => e.employee)
	const assign = () =>
		dialog.confirm({
			title: "Confirm",
			message: `Assign Salary Structure to ${employees.length} employee(s)?`,
			confirmLabel: "Yes",
			onConfirm: () => run(employees),
		})
	if (!noBase.length) return assign()
	dialog.confirm({
		title: "Are you sure you want to proceed?",
		message: `Base amount has not been set for the following employee(s): ${noBase.join(", ")}`,
		confirmLabel: "Continue",
		onConfirm: assign,
	})
}

async function run(employees: { employee: string; base: number; variable: number }[]) {
	busy.value = true
	try {
		const res = await api<RunResult>(`${API}.bulk_assign`, { values: doc.value, employees })
		if (res.queued) {
			toast.info("Creation of Salary Structure Assignments has been queued. It may take a few minutes.")
			return
		}
		const created = res.created || []
		const failed = res.failed || []
		const title = failed.length ? (created.length ? "Partial Success" : "Failure") : "Success"
		result.value = { title, created, failed }
		if (created.length) await loadRows()
	} catch {
		// The api helper already showed the server's message
	} finally {
		busy.value = false
	}
}
</script>
