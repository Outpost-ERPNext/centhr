<template>
	<div class="flex flex-col gap-3 px-5 py-3">
		<div class="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:grid-cols-7">
			<StatCard
				v-for="card in cards"
				:key="card.key"
				clickable
				:active="category === card.key"
				:label="card.label"
				:value="`${card.count}`"
				:tone="card.tone"
				:loading="loading"
				@click="category = card.key"
			/>
		</div>

		<div class="flex flex-wrap items-center gap-2">
			<div class="relative w-full sm:w-64">
				<span class="lucide-search pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-ch-ink-3" />
				<input v-model="search" class="h-8 w-full rounded-4 border border-ch-line bg-ch-surface pl-7 pr-2 text-[13px]" placeholder="Search reports…" />
			</div>
			<span class="text-[13px] text-ch-ink-3">{{ shown.length }} reports</span>
			<SegmentedTabs v-model="layout" class="ml-auto" :tabs="[{ label: 'Grid', value: 'grid' }, { label: 'Table', value: 'table' }]" />
		</div>

		<p v-if="error" class="text-[13px] text-ch-red-ink">{{ error }}</p>
		<template v-for="group in groups" :key="group.category">
			<h3 class="mt-1 flex items-center gap-2 text-[14px] font-medium text-ch-ink">
				{{ group.category }} <span class="rounded-full bg-ch-subtle px-2 text-[12px] text-ch-ink-3">{{ group.reports.length }}</span>
			</h3>
			<div :class="layout === 'grid' ? 'grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4' : 'flex flex-col divide-y divide-ch-line rounded-5 border border-ch-line bg-ch-surface'">
				<div
					v-for="report in group.reports"
					:key="report.name"
					class="flex items-center gap-2 px-3 py-2.5 text-[13px]"
					:class="layout === 'grid' ? 'rounded-5 border border-ch-line bg-ch-surface' : ''"
				>
					<span class="lucide-file-text size-4 shrink-0 text-ch-ink-3" />
					<a :href="report.route" target="_blank" class="min-w-0 flex-1 truncate font-medium text-ch-ink hover:underline" :title="report.name">{{ report.name }}</a>
					<span v-if="layout === 'table'" class="hidden text-ch-ink-3 sm:block">{{ report.ref_doctype }} · {{ report.report_type }}</span>
					<button
						type="button"
						class="size-4 shrink-0"
						:class="favourites.includes(report.name) ? 'lucide-star text-ch-amber-dot' : 'lucide-star text-ch-ink-4 hover:text-ch-ink-2'"
						:aria-pressed="favourites.includes(report.name)"
						:aria-label="`Favourite ${report.name}`"
						@click="toggleFavourite(report.name)"
					/>
					<a :href="report.route" target="_blank" class="lucide-arrow-up-right size-4 shrink-0 text-ch-primary" :aria-label="`Open ${report.name}`" />
				</div>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatCard from "@/components/StatCard.vue"
import { getReports, useTabData, type Scope } from "@/data/payrollDashboard"
import type { Tone } from "@/utils/status"
import { readStorage, writeStorage } from "@/utils/storage"

const props = defineProps<{ scope: Scope }>()
const { data, loading, error } = useTabData(props.scope, () => getReports())

const FAVOURITES = "Favourites"
const TONES: Record<string, Tone> = { Payroll: "blue", Attendance: "amber", Leaves: "green", "HR & Staff": "gray", Advances: "red" }

const category = ref("all")
const search = ref("")
const layout = ref(readStorage("centhr-reports-layout", "grid"))
const favourites = ref<string[]>(readFavourites())
watch(layout, (v) => writeStorage("centhr-reports-layout", v))

const reports = computed(() => data.value || [])
const categories = computed(() => [...new Set(reports.value.map((r) => r.category))])
const cards = computed(() => [
	{ key: "all", label: "All reports", count: reports.value.length, tone: undefined },
	...categories.value.map((c) => ({ key: c, label: c, count: reports.value.filter((r) => r.category === c).length, tone: TONES[c] })),
	{ key: FAVOURITES, label: FAVOURITES, count: favourites.value.length, tone: "amber" as Tone },
])
const shown = computed(() => {
	const term = search.value.trim().toLowerCase()
	return reports.value
		.filter((r) => category.value === "all" || r.category === category.value || (category.value === FAVOURITES && favourites.value.includes(r.name)))
		.filter((r) => !term || r.name.toLowerCase().includes(term) || r.ref_doctype.toLowerCase().includes(term))
})
// Favourites first within each category
const groups = computed(() =>
	categories.value
		.map((c) => ({
			category: c,
			reports: shown.value
				.filter((r) => r.category === c)
				.sort((a, b) => Number(favourites.value.includes(b.name)) - Number(favourites.value.includes(a.name))),
		}))
		.filter((g) => g.reports.length)
)

function readFavourites(): string[] {
	try {
		const saved = JSON.parse(readStorage("centhr-report-favourites", "[]"))
		return Array.isArray(saved) ? saved : []
	} catch {
		return []
	}
}

function toggleFavourite(name: string) {
	favourites.value = favourites.value.includes(name) ? favourites.value.filter((f) => f !== name) : [...favourites.value, name]
	writeStorage("centhr-report-favourites", JSON.stringify(favourites.value))
}
</script>
