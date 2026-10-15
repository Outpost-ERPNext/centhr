<template>
	<PageHeader :crumbs="[{ label: 'Shift' }]">
		<template #actions>
			<Button
				v-if="can('Shift Type').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New shift"
				:route="{ name: 'ShiftTypeNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search shifts"
		noun="shift"
		@clear="list.clearFilters"
	>
		<FilterSelect
			v-if="readable('enable_auto_attendance')"
			v-model="list.state.filters.auto_attendance"
			:options="[
				{ label: 'On', value: '1' },
				{ label: 'Off', value: '0' },
			]"
			placeholder="Auto attendance"
		/>
		<FilterLink
			v-if="canReadAssignments"
			v-model="list.state.filters.company"
			doctype="Company"
			placeholder="Entity"
		/>
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-timer"
		:empty-message="hasFilters ? 'No shifts match these filters' : 'No shifts created yet'"
		:mobile-aside="canReadAssignments ? 'assigned' : undefined"
		min-width="820px"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/shifts/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-timer size-4" />
				</span>
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
					<div v-if="row.start_time" class="truncate text-[12px] text-ch-ink-3 md:hidden">
						{{ shiftTiming(row.start_time, row.end_time) }}
					</div>
				</div>
			</div>
		</template>
		<template #cell-timing="{ row }">
			<span v-if="row.start_time" class="flex min-w-0 items-center gap-2 text-ch-ink-2">
				<span class="lucide-clock size-3.5 shrink-0 text-ch-ink-3" />
				<span class="truncate">{{ shiftTiming(row.start_time, row.end_time) }}</span>
			</span>
			<span v-else class="text-ch-ink-4">—</span>
		</template>
		<template #cell-assigned="{ row }">
			<span class="whitespace-nowrap text-ch-ink-2">{{ assignedLabel(row) }}</span>
		</template>
		<template #cell-enable_auto_attendance="{ row }">
			<span class="flex items-center gap-1.5 whitespace-nowrap">
				<span
					class="size-2 shrink-0 rounded-full"
					:class="row.enable_auto_attendance ? 'bg-ch-green-dot' : 'bg-ch-gray-dot'"
				/>
				{{ row.enable_auto_attendance ? "On" : "Off" }}
			</span>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<p class="px-4 pb-6 text-[12.5px] text-ch-ink-3 sm:px-5">
		Employees get a shift through submitted Shift Assignments. Weekly offs come from the shift's holiday list, or
		from the employee's or company's default when it has none.
	</p>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import { useDocList, type Filter } from "@/data/list"
import { can, getReadableFields } from "@/data/permissions"
import { getShiftAssignmentSummary, getShiftTypesForCompany, type ShiftAssignmentSummary } from "@/data/shift"
import { shiftTiming } from "@/utils/format"

const router = useRouter()

// Shift Type has no company or assignee count; both come from its Shift Assignments,
// shown only to users the Role Permission Manager lets read them
const canReadAssignments = computed(() => can("Shift Assignment").read)

// Ask only for fields the user may read (permlevel), so a permission change cannot break the list
const readableFields = ref<string[]>([])
const ready = getReadableFields("Shift Type").then((fields) => (readableFields.value = fields))
const readable = (field: string) => !readableFields.value.length || readableFields.value.includes(field)

const FIELDS = ["start_time", "end_time", "holiday_list", "enable_auto_attendance"]

const list = useDocList({
	doctype: "Shift Type",
	fields: () => ["name", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: async (state) => {
		const f = state.filters
		const filters: Filter[] = []
		if (f.auto_attendance && readable("enable_auto_attendance")) {
			filters.push(["enable_auto_attendance", "=", Number(f.auto_attendance)])
		}
		if (f.company && canReadAssignments.value) {
			const names = await getShiftTypesForCompany(f.company)
			// No match must show no rows, not every row
			filters.push(["name", "in", names.length ? names : [""]])
		}
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const assignments = ref<Record<string, ShiftAssignmentSummary>>({})
watch(
	() => list.rows.value,
	async (rows) => {
		const names = rows.map((r: Record<string, any>) => r.name)
		assignments.value = canReadAssignments.value ? await getShiftAssignmentSummary(names) : {}
	}
)

function assignedLabel(row: Record<string, any>) {
	const n = assignments.value[row.name]?.employees || 0
	return `${n} ${n === 1 ? "employee" : "employees"}`
}

const columns = computed<Column[]>(() => [
	{ key: "name", label: "Shift", width: "minmax(180px,1.6fr)", sortable: true },
	...(readable("start_time")
		? [{ key: "timing", label: "Timing", width: "minmax(190px,1.6fr)", hideOnMobile: true } as Column]
		: []),
	...(readable("holiday_list")
		? [
				{
					key: "holiday_list",
					label: "Holiday list",
					width: "minmax(150px,1.3fr)",
					sortable: true,
					hideOnMobile: true,
					format: (v: any) => v || "Employee / company default",
				} as Column,
			]
		: []),
	...(canReadAssignments.value
		? [
				{
					key: "company",
					label: "Entity",
					width: "minmax(150px,1.3fr)",
					hideOnMobile: true,
					format: (_: any, row: Record<string, any>) => assignments.value[row.name]?.companies.join(", ") || "—",
				} as Column,
				{
					key: "assigned",
					label: "Assigned",
					width: "minmax(110px,0.9fr)",
					align: "right",
					format: (_: any, row: Record<string, any>) => assignedLabel(row),
				} as Column,
			]
		: []),
	...(readable("enable_auto_attendance")
		? [
				{
					key: "enable_auto_attendance",
					label: "Auto attendance",
					width: "minmax(120px,0.9fr)",
					sortable: true,
					// Used by the stacked mobile row; the desktop cell has its own slot
					format: (v: any) => (v ? "Auto attendance on" : "Auto attendance off"),
				} as Column,
			]
		: []),
])
</script>
