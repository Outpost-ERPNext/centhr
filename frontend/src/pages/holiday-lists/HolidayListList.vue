<template>
	<PageHeader :crumbs="[{ label: 'Holiday List' }]">
		<template #actions>
			<Button
				v-if="can('Holiday List').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New holiday list"
				:route="{ name: 'HolidayListNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search holiday lists"
		noun="holiday list"
		@clear="list.clearFilters"
	>
		<FilterSelect v-if="readable('from_date')" v-model="list.state.filters.year" :options="years" placeholder="Year" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-calendar-off"
		:empty-message="hasFilters ? 'No holiday lists match these filters' : 'No holiday lists created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/holiday-lists/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-calendar-off size-4" />
				</span>
				<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
			</div>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<p class="px-4 pb-6 text-[12.5px] text-ch-ink-3 sm:px-5">
		Employees get holidays from their Holiday List Assignment, or from the holiday list on the employee, shift or
		company.
	</p>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import { useDocList, type Filter } from "@/data/list"
import { can, useReadableFields } from "@/data/permissions"
import { formatDateShort, formatNumber } from "@/utils/format"

const router = useRouter()

const { ready, readable } = useReadableFields("Holiday List")
const FIELDS = ["from_date", "to_date", "total_holidays", "weekly_off"]

const list = useDocList({
	doctype: "Holiday List",
	fields: () => ["name", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["name"],
	defaultSort: { field: "from_date", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		const year = Number(state.filters.year)
		// A list belongs to every year its period touches
		if (year && readable("from_date")) {
			filters.push(["from_date", "<=", `${year}-12-31`], ["to_date", ">=", `${year}-01-01`])
		}
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const thisYear = new Date().getFullYear()
const years = Array.from({ length: 6 }, (_, i) => String(thisYear + 1 - i)).map((y) => ({ label: y, value: y }))

const columns = computed<Column[]>(() =>
	[
		{ key: "name", label: "Holiday list", width: "minmax(200px,2fr)", sortable: true },
		{
			key: "from_date",
			label: "Period",
			width: "minmax(180px,1.6fr)",
			sortable: true,
			format: (_: any, row: Record<string, any>) => `${formatDateShort(row.from_date)} – ${formatDateShort(row.to_date)}`,
		},
		{ key: "weekly_off", label: "Weekly off", width: "minmax(110px,1fr)", sortable: true, hideOnMobile: true, format: (v: any) => v || "—" },
		{
			key: "total_holidays",
			label: "Holidays",
			width: "minmax(90px,0.8fr)",
			align: "right" as const,
			sortable: true,
			format: (v: any) => formatNumber(v),
		},
	].filter((c) => c.key === "name" || readable(c.key))
)
</script>
