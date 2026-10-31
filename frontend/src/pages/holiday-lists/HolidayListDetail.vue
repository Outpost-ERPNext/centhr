<template>
	<DocPageShell
		doctype="Holiday List"
		list-label="Holiday List"
		:page="page"
		:title="page.doc.value.holiday_list_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : period"
		:hidden-fields="hiddenFields"
		:field-options="fieldOptions"
		:buttons="buttons"
		@change="onChange"
	>
		<template #avatar>
			<span
				v-if="!page.isNew"
				class="flex size-10 shrink-0 items-center justify-center rounded-4 bg-ch-surface text-ch-ink-2 shadow-ch-xs"
			>
				<span class="lucide-calendar-off size-5" />
			</span>
		</template>
		<template #status><span /></template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<SummaryCard
				title="Details"
				:items="[
					{ label: 'Period', value: period },
					{ label: 'Total holidays', value: formatNumber(page.doc.value.total_holidays) },
					{ label: 'Weekly offs', value: String(weeklyOffs) },
					{ label: 'Other holidays', value: String((page.doc.value.holidays?.length || 0) - weeklyOffs) },
					{ label: 'Country', value: countryLabel },
					{ label: 'Subdivision', value: page.doc.value.subdivision },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { toast } from "frappe-ui"
import DocPageShell from "@/components/DocPageShell.vue"
import type { FormButton } from "@/components/DocForm.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { api } from "@/data/api"
import { useDocPage } from "@/data/useDocPage"
import { addDays, formatDateShort, formatNumber, parseDate, toISODate } from "@/utils/format"

type Option = { label: string; value: string }

const props = defineProps<{ name: string | null }>()
const busy = ref<string | null>(null)

const page = useDocPage("Holiday List", props.name, { onLoaded: updateTotal })

// The ERPNext form script (holiday_list.js) loads these on refresh and fills the pickers with set_data
const countries = ref<Option[]>([])
const subdivisionsByCountry = ref<Record<string, string[]>>({})
api<{ countries: Option[]; subdivisions_by_country: Record<string, string[]> }>(
	"centhr.api.holiday_list.get_supported_countries",
	{},
	{ silent: true }
)
	.then((res) => {
		countries.value = res.countries.sort((a, b) => a.label.localeCompare(b.label))
		subdivisionsByCountry.value = res.subdivisions_by_country
	})
	.catch(() => undefined)

const subdivisions = computed(() => subdivisionsByCountry.value[page.doc.value.country] || [])
const fieldOptions = computed(() => ({
	country: countries.value,
	subdivision: subdivisions.value.map((s) => ({ label: s, value: s })),
}))
// As in Desk, Subdivision shows only for a country that has subdivisions
const hiddenFields = computed(() => (subdivisions.value.length ? [] : ["subdivision"]))

/** The form's Button fields, which run the document method of the same name. */
const buttons = computed<Record<string, FormButton>>(() =>
	Object.fromEntries(
		["get_weekly_off_dates", "get_local_holidays", "clear_table"].map((method) => [
			method,
			{ onClick: () => updateHolidays(method), loading: busy.value === method, disabled: !!busy.value },
		])
	)
)

function onChange(fieldname: string) {
	const d = page.doc.value
	if (fieldname === "from_date" && d.from_date && !d.to_date) {
		// A year from the start date, like the Desk form
		d.to_date = addDays(addMonthsISO(d.from_date, 12), -1)
	} else if (fieldname === "country") {
		d.subdivision = ""
		addLocalHolidays()
	} else if (fieldname === "subdivision") {
		addLocalHolidays()
	} else if (fieldname === "holidays") {
		updateTotal()
	}
}

// Dates the automatic fill added and that are not saved yet, so a new country or subdivision replaces them
const autoAdded = new Set<string>()

/**
 * Picking a country or subdivision adds its public holidays right away; the button can run it again.
 * The holidays added for the previous choice go, unless they were saved.
 */
function addLocalHolidays() {
	queue = queue.then(async () => {
		const d = page.doc.value
		d.holidays = (d.holidays || []).filter((h: Record<string, any>) => h.name || !autoAdded.has(h.holiday_date))
		autoAdded.clear()
		updateTotal()
		if (!d.country || !d.from_date || !d.to_date) return
		const before = new Set((d.holidays || []).map((h: Record<string, any>) => h.holiday_date))
		await runTableMethod("get_local_holidays")
		for (const h of page.doc.value.holidays || []) if (!before.has(h.holiday_date)) autoAdded.add(h.holiday_date)
	})
}

function updateTotal() {
	const holidays: Record<string, any>[] = page.doc.value.holidays || []
	page.doc.value.total_holidays = holidays.reduce((sum, h) => sum + (h.is_half_day ? 0.5 : 1), 0)
}

/** Runs a table button on the unsaved form; the server changes the table and the user saves it. Calls run one at a time. */
let queue: Promise<void> = Promise.resolve()
function updateHolidays(method: string) {
	queue = queue.then(() => runTableMethod(method))
	return queue
}

async function runTableMethod(method: string) {
	busy.value = method
	try {
		const res = await api<{ holidays: Record<string, any>[]; total_holidays: number }>(
			"centhr.api.holiday_list.update_holidays",
			{ doc: page.doc.value, method }
		)
		const before = page.doc.value.holidays?.length || 0
		// In date order, as the server sorts them on save; new rows would otherwise sit at the bottom
		const holidays = [...res.holidays].sort((a, b) => String(a.holiday_date).localeCompare(String(b.holiday_date)))
		holidays.forEach((row, i) => (row.idx = i + 1))
		page.doc.value.holidays = holidays
		page.doc.value.total_holidays = res.total_holidays

		const added = holidays.length - before
		if (method === "clear_table") toast.success("Holidays table cleared. Save to keep the change.")
		else if (added > 0) toast.success(`Added ${added} ${added === 1 ? "holiday" : "holidays"}. Save to keep them.`)
		else toast.info("No new holidays to add. Every date is already in the table.")
	} catch {
		// The api helper already showed the server's message
	} finally {
		busy.value = null
	}
}

/** frappe.datetime.add_months: the day is capped at the end of a shorter month. */
function addMonthsISO(value: string, months: number) {
	const date = parseDate(value)!
	const target = new Date(date.getFullYear(), date.getMonth() + months, 1)
	const lastDay = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
	target.setDate(Math.min(date.getDate(), lastDay))
	return toISODate(target)
}

const weeklyOffs = computed(() => (page.doc.value.holidays || []).filter((h: Record<string, any>) => h.weekly_off).length)
const period = computed(() => `${formatDateShort(page.doc.value.from_date)} – ${formatDateShort(page.doc.value.to_date)}`)
const countryLabel = computed(
	() => countries.value.find((c) => c.value === page.doc.value.country)?.label || page.doc.value.country
)
</script>
