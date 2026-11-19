<template>
	<Dialog v-model:open="open" title="Master payroll Excel reconciliation" size="6xl">
		<div class="flex flex-col gap-4 text-[13px]">
			<div class="flex flex-wrap items-center gap-2">
				<p class="mr-auto max-w-xl text-ch-ink-3">
					Finance's payroll sheet for {{ cycleLabel(scope.from, scope.to) }} against the salary slips here: net pay, gross pay, total
					deduction and paid days.
				</p>
				<input ref="input" type="file" accept=".xlsx,.csv" class="hidden" @change="pick" />
				<Button icon-left="lucide-download" label="Template" @click="downloadMasterTemplate(scope)" />
				<Button
					v-if="sheet"
					icon-left="lucide-columns-3"
					label="Map columns"
					:tooltip="scope.company ? undefined : 'Choose a company to map the columns of its sheet'"
					:disabled="!scope.company"
					@click="mappingOpen = true"
				/>
				<Button variant="solid" icon-left="lucide-upload" :label="sheet ? 'Replace Excel' : 'Upload Excel'" :loading="busy" @click="input?.click()" />
				<Button v-if="sheet" theme="red" icon-left="lucide-trash-2" label="Remove" :disabled="busy" @click="confirmRemove" />
			</div>
			<p v-if="error" class="rounded-4 bg-ch-red-bg px-3 py-2 text-ch-red-ink" role="alert">{{ error }}</p>

			<template v-if="sheet && result">
				<div class="flex flex-wrap items-center gap-2 rounded-4 border border-ch-line px-3 py-2">
					<span class="lucide-file-spreadsheet size-4 shrink-0 text-ch-ink-3" />
					<span class="truncate font-medium text-ch-ink">{{ sheet.file_name }}</span>
					<span class="text-ch-ink-3">{{ sheetNote }}</span>
					<Button class="ml-auto" size="sm" icon-left="lucide-download" label="Download" :href="sheet.file_url" />
				</div>

				<div v-if="result.problem" class="flex flex-wrap items-center gap-2 rounded-4 bg-ch-amber-bg px-3 py-2 text-ch-amber-ink" role="alert">
					<span class="lucide-triangle-alert size-4 shrink-0" />
					<span class="flex-1">{{ result.problem }}</span>
					<Button v-if="scope.company" size="sm" label="Map columns" @click="mappingOpen = true" />
				</div>
				<template v-else>
					<div class="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
						<StatCard v-for="tile in tiles" :key="tile.label" :label="tile.label" :value="formatNumber(tile.value)" :tone="tile.tone" />
					</div>
					<p v-if="result.ignored" class="rounded-4 bg-ch-subtle px-3 py-2 text-ch-ink-2">
						{{ result.ignored }} rows of the sheet have no net pay and were not compared.
					</p>
					<ReconcileResultTable :scope="scope" :rows="result.rows || []" :summary="result.summary!" />
				</template>
			</template>
			<div v-else-if="loading" class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
			<div v-else class="flex flex-col items-center gap-2 rounded-4 border border-dashed border-ch-line px-4 py-10 text-center">
				<span class="lucide-file-spreadsheet size-6 text-ch-ink-4" />
				<p class="font-medium text-ch-ink">No master sheet for this cycle yet</p>
				<p class="max-w-md text-ch-ink-3">
					Upload an .xlsx or .csv file. Its first row names the columns; Employee ID and Net Pay are needed. If its headers differ, map
					them after the upload.
				</p>
			</div>

			<p class="text-[12px] text-ch-ink-3">The master sheet is kept per pay cycle. Another company or cycle shows its own sheet.</p>
		</div>
	</Dialog>

	<MasterSheetColumnsDialog v-if="sheet" v-model:open="mappingOpen" :scope="scope" @saved="result = $event" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Dialog, LoadingIndicator, dialog, toast } from "frappe-ui"
import StatCard from "@/components/StatCard.vue"
import { downloadMasterTemplate, removeMasterSheet, uploadMasterSheet, type Reconciliation } from "@/data/masterSheet"
import { cycleLabel } from "@/data/payroll"
import type { Scope } from "@/data/payrollDashboard"
import { formatDateTime, formatNumber } from "@/utils/format"
import type { Tone } from "@/utils/status"
import MasterSheetColumnsDialog from "./MasterSheetColumnsDialog.vue"
import ReconcileResultTable from "./ReconcileResultTable.vue"

/** Finance's master payroll sheet of the cycle against its salary slips. The Processing tab loads the
 * result, so it also marks the slips in its grid. */
const props = defineProps<{ scope: Scope; loading?: boolean }>()
const open = defineModel<boolean>("open", { default: false })
const result = defineModel<Reconciliation | null>("result", { default: null })

const input = ref<HTMLInputElement | null>(null)
const mappingOpen = ref(false)
const busy = ref(false)
const error = ref("")

const sheet = computed(() => result.value?.sheet || null)
const sheetNote = computed(() => {
	const s = sheet.value!
	const size = s.file_size ? `${(s.file_size / 1024).toFixed(1)} KB · ` : ""
	return `${size}Uploaded ${formatDateTime(s.uploaded_on)} by ${s.uploaded_by}`
})
const tiles = computed<{ label: string; value: number; tone?: Tone }[]>(() => {
	const summary = result.value!.summary!
	return [
		{ label: "Total in Excel", value: summary.excel },
		{ label: "Total ERP slips", value: summary.slips },
		{ label: "Matched", value: summary.Matched, tone: "green" },
		{ label: "Discrepancies", value: summary.Discrepancy, tone: summary.Discrepancy ? "red" : undefined },
		{ label: "Missing in ERP", value: summary["Missing in ERP"], tone: summary["Missing in ERP"] ? "amber" : undefined },
		{ label: "Missing in Excel", value: summary["Missing in Excel"], tone: summary["Missing in Excel"] ? "amber" : undefined },
	]
})

async function pick(event: Event) {
	const target = event.target as HTMLInputElement
	const file = target.files?.[0]
	// Picking the same file again must fire the change event too
	target.value = ""
	if (!file) return
	busy.value = true
	error.value = ""
	try {
		result.value = await uploadMasterSheet(props.scope, file)
	} catch (e: any) {
		error.value = e?.message || "Could not read the sheet"
	} finally {
		busy.value = false
	}
}

function confirmRemove() {
	dialog.confirm({
		title: "Remove master sheet",
		message: `Remove ${sheet.value!.file_name} from ${cycleLabel(props.scope.from, props.scope.to)}? The salary slips are not changed.`,
		confirmLabel: "Remove",
		theme: "red",
		onConfirm: async () => {
			await removeMasterSheet(props.scope)
			result.value = { sheet: null }
			toast.success("Master sheet removed")
		},
	})
}
</script>
