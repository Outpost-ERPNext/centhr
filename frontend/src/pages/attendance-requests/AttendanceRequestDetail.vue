<template>
	<DocPageShell
		doctype="Attendance Request"
		list-label="Attendance Request"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.employee || page.doc.value.name"
		:subtitle="page.isNew ? '' : period"
		:hidden-fields="['amended_from']"
		:link-filters="linkFilters"
		:link-queries="{ employee: 'erpnext.controllers.queries.employee_query' }"
		@change="onChange"
	>
		<template #status>
			<span v-if="!page.isNew" class="flex items-center gap-2">
				<StatusBadge pill doctype="Attendance Request" :status="page.doc.value.reason" />
				<StatusBadge pill :status="docstatusLabel(page.docstatus.value)" />
			</span>
		</template>
		<template #before-form>
			<p class="text-[13px] text-ch-ink-3">
				On submission, attendance is marked as {{ page.doc.value.reason || "Work From Home or On Duty" }} for each
				day of the period. Holidays are skipped unless Include Holidays is ticked, and days on leave are skipped.
			</p>
		</template>
		<!-- The Desk form's "Attendance Warnings" dashboard for a draft -->
		<template v-if="warnings.length" #notice>
			<section class="flex flex-col gap-2 rounded-5 border border-ch-line bg-ch-amber-bg p-4 text-[13px]">
				<p class="text-ch-amber-ink">Attendance for the following dates will be skipped/overwritten on submission</p>
				<div class="overflow-x-auto rounded-4 border border-ch-line bg-ch-surface">
					<table class="w-full text-left">
						<thead class="bg-ch-subtle text-ch-ink-3">
							<tr>
								<th class="px-3 py-1.5 font-normal">Date</th>
								<th class="px-3 py-1.5 font-normal">Action on Submission</th>
								<th class="px-3 py-1.5 font-normal">Reason</th>
								<th class="px-3 py-1.5 font-normal">Existing Record</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="w in warnings" :key="w.date" class="border-t border-ch-line">
								<td class="px-3 py-1.5">{{ formatDate(w.date) }}</td>
								<td class="px-3 py-1.5">{{ w.action }}</td>
								<td class="px-3 py-1.5">{{ w.reason }}</td>
								<td class="px-3 py-1.5">
									<RouterLink
										v-if="w.record"
										:to="routeFor('Attendance', w.record)!"
										class="underline-offset-2 hover:underline"
									>
										{{ w.record }}
									</RouterLink>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Request"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Department', value: page.doc.value.department },
					{ label: 'Period', value: period },
					{ label: 'Days', value: String(days) },
					{ label: 'Half day', value: page.doc.value.half_day ? formatDate(page.doc.value.half_day_date) : null },
					{ label: 'Shift', value: page.doc.value.shift, route: routeFor('Shift Type', page.doc.value.shift) },
					{ label: 'Include holidays', value: page.doc.value.include_holidays ? 'Yes' : 'No' },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { api } from "@/data/api"
import { useDocPage } from "@/data/useDocPage"
import { formatDate, formatDateShort, parseDate } from "@/utils/format"
import { routeFor } from "@/utils/routes"
import { docstatusLabel } from "@/utils/status"

interface Warning {
	date: string
	reason: string
	action: string
	record?: string
}

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const warnings = ref<Warning[]>([])

const page = useDocPage("Attendance Request", props.name, {
	defaults: () => {
		const values: Record<string, any> = {}
		for (const key of ["employee", "company"]) if (route.query[key]) values[key] = route.query[key]
		return values
	},
	onLoaded: loadWarnings,
})

// Only active employees of the chosen company
const linkFilters = {
	employee: (doc: Record<string, any>) => ({ status: "Active", ...(doc.company ? { company: doc.company } : {}) }),
}

/** show_attendance_warnings of the Desk form: dates a submitted draft would skip or overwrite. */
async function loadWarnings() {
	warnings.value = []
	if (page.isNew || page.docstatus.value !== 0) return
	const res = await api<Warning[]>(
		"frappe.handler.run_doc_method",
		{ dt: "Attendance Request", dn: page.doc.value.name, method: "get_attendance_warnings" },
		{ silent: true }
	).catch(() => null)
	warnings.value = res || []
}
// After a save or submit the warnings change, or go away
watch(() => `${page.doc.value.modified}|${page.docstatus.value}`, loadWarnings)

/** The Desk form fills the shift from the employee's shift assignment on the start date when it is empty. */
async function onChange(fieldname: string) {
	const d = page.doc.value
	if (!["employee", "from_date"].includes(fieldname) || !d.employee || !d.from_date || d.shift) return
	const shift = await api<string | null>(
		"hrms.hr.doctype.attendance.attendance.get_employee_shift",
		{ employee: d.employee, for_date: d.from_date },
		{ silent: true }
	).catch(() => null)
	if (shift && !page.doc.value.shift) page.doc.value.shift = shift
}

const period = computed(() => {
	const d = page.doc.value
	if (!d.from_date) return ""
	return d.from_date === d.to_date || !d.to_date
		? formatDateShort(d.from_date)
		: `${formatDateShort(d.from_date)} – ${formatDateShort(d.to_date)}`
})
const days = computed(() => {
	const from = parseDate(page.doc.value.from_date)
	const to = parseDate(page.doc.value.to_date)
	return from && to ? Math.round((to.getTime() - from.getTime()) / 86400000) + 1 : 0
})
</script>
