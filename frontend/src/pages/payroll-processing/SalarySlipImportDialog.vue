<template>
	<Dialog v-model:open="open" title="Import salary slips" size="lg">
		<div class="flex flex-col gap-4 text-[13px]">
			<!-- 1. Template -->
			<section class="flex flex-col gap-2">
				<h3 class="font-medium text-ch-ink">1. Download the template</h3>
				<p class="text-ch-ink-3">
					One row per salary slip. Fill Employee and the pay period; leave Earnings and Deductions empty and the amounts
					are calculated from the employee's salary structure, as in a payroll run. To give the amounts yourself, add
					one row per component under Earnings and Deductions and fill Salary Structure.
				</p>
				<div>
					<Button icon-left="lucide-download" label="Download Excel template" :href="templateUrl" />
				</div>
			</section>

			<!-- 2. Upload -->
			<section class="flex flex-col gap-2">
				<h3 class="font-medium text-ch-ink">2. Upload the filled file</h3>
				<label
					class="flex cursor-pointer items-center gap-3 rounded-4 border border-dashed border-ch-line-2 px-4 py-3 hover:bg-ch-subtle"
					:class="{ 'pointer-events-none opacity-60': busy || importing }"
				>
					<span class="lucide-file-spreadsheet size-5 shrink-0 text-ch-ink-3" />
					<span class="min-w-0 flex-1 truncate" :class="file ? 'text-ch-ink' : 'text-ch-ink-3'">
						{{ file ? file.name : "Choose an .xlsx or .csv file" }}
					</span>
					<input type="file" accept=".xlsx,.csv" class="sr-only" @change="pickFile" />
				</label>
				<div v-if="preview" class="rounded-4 bg-ch-subtle px-3 py-2">
					<p class="text-ch-ink">
						{{ formatNumber(preview.count) }} salary slip{{ preview.count === 1 ? "" : "s" }} found in the file.
					</p>
					<ul v-if="preview.warnings.length" class="mt-1.5 flex max-h-40 list-disc flex-col gap-0.5 overflow-y-auto pl-4 text-ch-amber-ink">
						<li v-for="(w, i) in preview.warnings" :key="i">{{ w }}</li>
					</ul>
					<p v-if="blocking" class="mt-1.5 text-ch-ink-2">Fix these in the file and upload it again.</p>
				</div>
			</section>

			<!-- 3. Result -->
			<section v-if="status" class="flex flex-col gap-2">
				<h3 class="font-medium text-ch-ink">3. Import</h3>
				<div class="flex items-center gap-2">
					<LoadingIndicator v-if="importing" class="size-4 text-ch-ink-3" />
					<StatusBadge pill :tone="statusTone" :status="status.status" />
					<span class="tabular-nums text-ch-ink-2">
						{{ formatNumber(status.success || 0) }} created<template v-if="status.failed">
							· {{ formatNumber(status.failed) }} failed</template
						>
						of {{ formatNumber(status.total_records || preview?.count || 0) }}
					</span>
				</div>
				<ul v-if="failures.length" class="flex max-h-48 flex-col gap-1 overflow-y-auto rounded-4 border border-ch-line p-2">
					<li v-for="(f, i) in failures" :key="i" class="text-ch-ink-2">
						<span class="font-medium text-ch-red-ink">Row {{ f.rows }}:</span> {{ f.message }}
					</li>
				</ul>
				<div v-if="status.failed && !importing">
					<Button size="sm" icon-left="lucide-download" label="Download failed rows" :href="failedRowsUrl" />
				</div>
			</section>

			<ErrorMessage :message="error" />
		</div>

		<template #actions>
			<div class="flex justify-end gap-2">
				<Button :label="done ? 'Close' : 'Cancel'" :disabled="busy" @click="open = false" />
				<Button
					v-if="!done"
					variant="solid"
					label="Import as draft"
					:loading="busy || importing"
					:disabled="!preview?.count || !!blocking"
					@click="startImport"
				/>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { Button, Dialog, ErrorMessage, LoadingIndicator, toast } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { api, errorMessage, stripHtml } from "@/data/api"
import { insertDoc } from "@/data/doc"
import { formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"

const open = defineModel<boolean>("open", { default: false })
const emit = defineEmits<{ imported: [] }>()

const DATA_IMPORT = "frappe.core.doctype.data_import.data_import"
const FINISHED = ["Success", "Partial Success", "Error", "Timed Out"]

// The columns of the template: the slip, plus its earnings and deductions
const TEMPLATE_FIELDS = {
	"Salary Slip": ["employee", "posting_date", "payroll_frequency", "start_date", "end_date", "company", "salary_structure"],
	earnings: ["salary_component", "amount"],
	deductions: ["salary_component", "amount"],
}
const templateUrl = `/api/method/${DATA_IMPORT}.download_template?${new URLSearchParams({
	doctype: "Salary Slip",
	file_type: "Excel",
	export_records: "blank_template",
	export_fields: JSON.stringify(TEMPLATE_FIELDS),
})}`

const file = ref<File | null>(null)
const dataImport = ref<string | null>(null)
const preview = ref<{ count: number; warnings: string[] } | null>(null)
const blocking = ref(false)
const status = ref<{ status: string; success?: number; failed?: number; total_records?: number } | null>(null)
const failures = ref<{ rows: string; message: string }[]>([])
const busy = ref(false)
const importing = ref(false)
const error = ref("")
let timer: ReturnType<typeof setTimeout> | undefined

const done = computed(() => !!status.value && FINISHED.includes(status.value.status))
const failedRowsUrl = computed(
	() => `/api/method/${DATA_IMPORT}.download_errored_template?${new URLSearchParams({ data_import_name: dataImport.value || "" })}`
)
const statusTone = computed<Tone>(() => {
	const s = status.value?.status
	return s === "Success" ? "green" : s === "Partial Success" ? "amber" : s === "Error" || s === "Timed Out" ? "red" : "blue"
})

// Every opening starts from a clean dialog
watch(open, (value) => {
	if (value) reset()
	else clearTimeout(timer)
})
onBeforeUnmount(() => clearTimeout(timer))

function reset() {
	clearTimeout(timer)
	file.value = null
	dataImport.value = null
	preview.value = null
	blocking.value = false
	status.value = null
	failures.value = []
	error.value = ""
	importing.value = false
}

async function pickFile(event: Event) {
	const input = event.target as HTMLInputElement
	const picked = input.files?.[0]
	input.value = ""
	if (!picked) return
	reset()
	file.value = picked
	busy.value = true
	try {
		const fileUrl = await upload(picked)
		const doc = await insertDoc({
			doctype: "Data Import",
			reference_doctype: "Salary Slip",
			import_type: "Insert New Records",
			import_file: fileUrl,
			submit_after_import: 0,
			mute_emails: 1,
		})
		dataImport.value = doc.name
		const out = await api<{ warnings: { message: string; type?: string; row?: number }[]; total_number_of_rows: number }>(
			`${DATA_IMPORT}.get_preview_from_template`,
			{ data_import: doc.name }
		)
		const warnings = (out?.warnings || [])
			.map((w) => (w.row ? `Row ${w.row}: ${stripHtml(w.message)}` : stripHtml(w.message)))
			.filter(Boolean)
		preview.value = { count: doc.payload_count || out?.total_number_of_rows || 0, warnings }
		// As in Frappe's Data Import, every warning but "info" stops the import until the file is fixed
		blocking.value = (out?.warnings || []).some((w) => w.type !== "info")
	} catch (e) {
		error.value = errorMessage(e)
	} finally {
		busy.value = false
	}
}

/** Salary data, so the file is private. */
async function upload(picked: File): Promise<string> {
	const form = new FormData()
	form.append("file", picked, picked.name)
	form.append("is_private", "1")
	form.append("folder", "Home")
	const response = await fetch("/api/method/upload_file", {
		method: "POST",
		body: form,
		headers: { "X-Frappe-CSRF-Token": window.csrf_token || "", Accept: "application/json" },
	})
	const body = await response.json().catch(() => ({}))
	if (!response.ok || !body.message?.file_url) {
		const messages = body._server_messages ? JSON.parse(body._server_messages).map((m: string) => JSON.parse(m).message) : []
		throw new Error(messages[0] || body.exception || "Could not upload the file")
	}
	return body.message.file_url
}

async function startImport() {
	if (!dataImport.value) return
	busy.value = true
	error.value = ""
	try {
		await api(`${DATA_IMPORT}.form_start_import`, { data_import: dataImport.value })
		importing.value = true
		status.value = { status: "In Progress" }
		poll()
	} catch (e) {
		error.value = errorMessage(e)
	} finally {
		busy.value = false
	}
}

/** The import runs in a background job; check on it until it ends. */
async function poll() {
	const name = dataImport.value
	if (!name || !open.value) return
	try {
		const next = await api(`${DATA_IMPORT}.get_import_status`, { data_import_name: name }, { silent: true })
		if (name !== dataImport.value) return
		status.value = next
		if (FINISHED.includes(next.status)) {
			importing.value = false
			await loadFailures(name)
			if (next.success) {
				toast.success(`${formatNumber(next.success)} salary slips imported as draft`)
				emit("imported")
			}
			return
		}
	} catch {
		// Keep polling; a passing network error should not end the import view
	}
	timer = setTimeout(poll, 2000)
}

async function loadFailures(name: string) {
	if (!status.value?.failed) return
	const logs = await api<{ row_indexes: string; messages: string; exception: string }[]>(
		`${DATA_IMPORT}.get_import_logs`,
		{ data_import: name, status: "failed" },
		{ silent: true }
	).catch(() => [])
	failures.value = logs.map((log) => ({
		rows: parseJson<number[]>(log.row_indexes, []).join(", "),
		message: logMessage(log),
	}))
}

function logMessage(log: { messages: string; exception: string }) {
	const messages = parseJson<any[]>(log.messages, [])
		.map((m) => stripHtml(typeof m === "string" ? m : m.message || ""))
		.filter(Boolean)
	if (messages.length) return messages.join(" ")
	// Without a message, the last line of the traceback names the error
	const lines = (log.exception || "").trim().split("\n")
	return lines[lines.length - 1] || "Could not import this row"
}

function parseJson<T>(value: string | null | undefined, fallback: T): T {
	try {
		return value ? JSON.parse(value) : fallback
	} catch {
		return fallback
	}
}
</script>
