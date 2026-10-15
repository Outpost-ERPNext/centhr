<template>
	<PageHeader :crumbs="[{ label: 'Leave Type' }]">
		<template #actions>
			<Button
				v-if="can('Leave Type').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New leave type"
				:route="{ name: 'LeaveTypeNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search leave type"
		noun="leave type"
		@clear="list.clearFilters"
	>
		<FilterSelect
			v-model="list.state.filters.kind"
			:options="[
				{ label: 'Carry forward', value: 'is_carry_forward' },
				{ label: 'Leave without pay', value: 'is_lwp' },
				{ label: 'Encashable', value: 'allow_encashment' },
				{ label: 'Earned leave', value: 'is_earned_leave' },
				{ label: 'Optional', value: 'is_optional_leave' },
			]"
			placeholder="Rule"
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
		empty-icon="lucide-tags"
		empty-message="No leave types match these filters"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/leave-types/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-calendar-days size-4" />
				</span>
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ leaveTypeRules(row) || "No special rules" }}</div>
				</div>
			</div>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import Pager from "@/components/Pager.vue"
import { getGroupCounts, useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { formatNumber } from "@/utils/format"
import { leaveTypeRules } from "./rules"

const router = useRouter()

const list = useDocList({
	doctype: "Leave Type",
	fields: [
		"name",
		"max_leaves_allowed",
		"max_continuous_days_allowed",
		"applicable_after",
		"is_carry_forward",
		"is_lwp",
		"is_ppl",
		"allow_encashment",
		"is_earned_leave",
		"is_optional_leave",
		"is_compensatory",
	],
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) => (state.filters.kind ? [[state.filters.kind, "=", 1] as Filter] : []),
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

// Two grouped counts cover every row on the page
const allocations = ref<Record<string, number>>({})
const applications = ref<Record<string, number>>({})
getGroupCounts("Leave Allocation", "leave_type", [["docstatus", "=", 1]]).then((c) => (allocations.value = c)).catch(() => undefined)
getGroupCounts("Leave Application", "leave_type", [["docstatus", "<", 2]]).then((c) => (applications.value = c)).catch(() => undefined)

const days = (v: any) => (v ? `${formatNumber(v)} d` : "—")

const columns: Column[] = [
	{ key: "name", label: "Leave type", width: "minmax(220px,2.4fr)", sortable: true },
	{ key: "max_leaves_allowed", label: "Max / year", width: "minmax(80px,1fr)", align: "right", sortable: true, format: days },
	{
		key: "max_continuous_days_allowed",
		label: "Max continuous",
		width: "minmax(100px,1fr)",
		align: "right",
		sortable: true,
		format: days,
	},
	{ key: "applicable_after", label: "Applicable after", width: "minmax(100px,1fr)", align: "right", sortable: true, format: (v) => (v ? `${v} working d` : "—") },
	{ key: "allocations", label: "Allocations", width: "minmax(80px,0.9fr)", align: "right", format: (_, row) => String(allocations.value[row.name] || 0) },
	{ key: "applications", label: "Applications", width: "minmax(80px,0.9fr)", align: "right", format: (_, row) => String(applications.value[row.name] || 0) },
]
</script>
