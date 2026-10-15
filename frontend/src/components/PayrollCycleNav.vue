<template>
	<div class="flex items-center gap-1">
		<Button icon="lucide-chevron-left" variant="ghost" aria-label="Previous payroll period" :disabled="busy || !from || !canStep(-1)" @click="step(-1)" />
		<div class="w-[5.5rem]" :title="yearHint">
			<Select :model-value="yearValue" :options="yearOptions" size="sm" aria-label="Payroll year" placeholder="Year" @update:model-value="pickYear(String($event))" />
		</div>
		<div class="w-[11.5rem] max-w-[46vw]" :title="hint">
			<Select :model-value="periodValue" :options="periodOptions" size="sm" aria-label="Payroll month" placeholder="Custom range" @update:model-value="pickPeriod(String($event))" />
		</div>
		<Button icon="lucide-chevron-right" variant="ghost" aria-label="Next payroll period" :disabled="busy || !to || !canStep(1)" @click="step(1)" />
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Select } from "frappe-ui"
import { cycleLabel, getPayrollCycle, getPayrollYears, type PayrollYear } from "@/data/payroll"
import { addDays, today } from "@/utils/format"

const props = defineProps<{ company: string | null | undefined; from?: string; to?: string; allowWholeYear?: boolean }>()
const emit = defineEmits<{ "update:from": [v: string]; "update:to": [v: string] }>()

const WHOLE_YEAR = "year"
const busy = ref(false)
const years = ref<PayrollYear[]>([])

// The year that holds the range start; the month picker lists that year's payroll months
const year = computed(() => years.value.find((y) => props.from && y.from_date <= props.from && props.from <= y.to_date))
const isWholeYear = computed(() => !!year.value && props.from === year.value.from_date && props.to === year.value.to_date)

const yearValue = computed(() => year.value?.from_date || "")
const yearOptions = computed(() => years.value.map((y) => ({ label: y.label, value: y.from_date })))
const periodValue = computed(() => {
	if (isWholeYear.value && props.allowWholeYear) return WHOLE_YEAR
	const match = year.value?.periods.find((p) => p.from_date === props.from && p.to_date === props.to)
	return match ? `${match.from_date}|${match.to_date}` : ""
})
const periodOptions = computed(() => {
	const months = (year.value?.periods || []).map((p) => ({ label: cycleLabel(p.from_date, p.to_date), value: `${p.from_date}|${p.to_date}` }))
	return props.allowWholeYear && year.value ? [{ label: "Whole year", value: WHOLE_YEAR }, ...months] : months
})

const yearHint = computed(() =>
	year.value
		? `${year.value.payroll_period || "Calendar year"} · ${cycleLabel(year.value.from_date, year.value.to_date)}`
		: undefined
)
const hint = computed(() =>
	year.value?.payroll_period
		? `Months from Payroll Period ${year.value.payroll_period}`
		: props.company
			? `${props.company} has no Payroll Period here, so calendar months are shown`
			: "Pick a company to follow its payroll period"
)

function setRange(from: string, to: string) {
	emit("update:from", from)
	emit("update:to", to)
}

let requestId = 0
async function goTo(date: string) {
	const id = ++requestId
	busy.value = true
	try {
		const cycle = await getPayrollCycle(props.company, date)
		if (id === requestId) setRange(cycle.from_date, cycle.to_date)
	} finally {
		if (id === requestId) busy.value = false
	}
}

function pickYear(value: string) {
	const picked = years.value.find((y) => y.from_date === value)
	if (!picked) return
	requestId++
	// The current month when it falls in the picked year, else the year's first month
	const now = today()
	const month = picked.periods.find((p) => p.from_date <= now && now <= p.to_date) || picked.periods[0]
	if (month) setRange(month.from_date, month.to_date)
	else setRange(picked.from_date, picked.to_date)
}

function pickPeriod(value: string) {
	requestId++
	if (value === WHOLE_YEAR && year.value) setRange(year.value.from_date, year.value.to_date)
	else if (value) {
		const [from, to] = value.split("|")
		setRange(from, to)
	}
}

/** In whole-year mode the arrows move between payroll years, so they stop at the first and last. */
function canStep(delta: number) {
	if (!(isWholeYear.value && props.allowWholeYear)) return true
	return !!years.value[years.value.indexOf(year.value!) - delta]
}

function step(delta: number) {
	if (isWholeYear.value && props.allowWholeYear) {
		// Whole year moves a year at a time (years are newest first)
		const index = years.value.indexOf(year.value!)
		const next = years.value[index - delta]
		if (next) setRange(next.from_date, next.to_date)
		return
	}
	goTo(delta < 0 ? addDays(props.from!, -1) : addDays(props.to!, 1))
}

// A new company starts at its current month; on first load keep a range already set (from the URL)
watch(
	() => props.company,
	async (company, old) => {
		const keep = old === undefined && props.from && props.to
		const list = await getPayrollYears(company)
		if (company !== props.company) return
		years.value = list
		if (!keep) goTo(today())
	},
	{ immediate: true }
)
</script>
