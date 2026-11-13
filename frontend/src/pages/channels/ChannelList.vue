<template>
	<PageHeader :crumbs="[{ label: 'Org Master', route: '/org-master' }, { label: 'Channel' }]">
		<template #actions>
			<Button
				v-if="can('Channel').create"
				variant="solid"
				icon-left="lucide-plus"
				label="New channel"
				:route="{ name: 'ChannelNew' }"
			/>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search channels"
		noun="channel"
		@clear="list.clearFilters"
	>
		<FilterSelect
			v-if="readable('disabled')"
			v-model="list.state.filters.disabled"
			:options="[
				{ label: 'Enabled', value: '0' },
				{ label: 'Disabled', value: '1' },
			]"
			placeholder="Status"
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
		empty-icon="lucide-radio-tower"
		:empty-message="hasFilters ? 'No channels match these filters' : 'No channels created yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(`/channels/${encodeURIComponent(row.name)}`)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-name="{ row }">
			<div class="flex min-w-0 items-center gap-2.5">
				<span class="flex size-8 shrink-0 items-center justify-center rounded-4 bg-ch-subtle text-ch-ink-2">
					<span class="lucide-radio-tower size-4" />
				</span>
				<div class="truncate font-medium text-ch-ink">{{ row.name }}</div>
			</div>
		</template>
		<template #cell-disabled="{ row }">
			<StatusBadge :status="row.disabled ? 'Disabled' : 'Enabled'" :tone="row.disabled ? 'gray' : 'green'" />
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
import StatusBadge from "@/components/StatusBadge.vue"
import { getGroupCounts, useDocList, type Filter } from "@/data/list"
import { can, useReadableFields } from "@/data/permissions"

const router = useRouter()

const { ready, readable } = useReadableFields("Channel")
const FIELDS = ["income_account", "expense_account", "enable_payment_approval", "disabled"]

const list = useDocList({
	doctype: "Channel",
	fields: () => ["name", ...FIELDS.filter(readable)],
	ready,
	searchFields: ["name"],
	defaultSort: { field: "name", order: "asc" },
	buildFilters: (state) =>
		state.filters.disabled && readable("disabled") ? [["disabled", "=", Number(state.filters.disabled)] as Filter] : [],
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

// One grouped count covers every row; empty when the user cannot read Employee
const employees = ref<Record<string, number>>({})
getGroupCounts("Employee", "channel", [["status", "=", "Active"]]).then((c) => (employees.value = c)).catch(() => undefined)

const columns = computed<Column[]>(() => [
	{ key: "name", label: "Channel", width: "minmax(200px,2fr)", sortable: true },
	...(
		[
			{ key: "income_account", label: "Income account", width: "minmax(160px,1.6fr)", sortable: true, hideOnMobile: true, format: (v: any) => v || "—" },
			{ key: "expense_account", label: "Expense account", width: "minmax(160px,1.6fr)", sortable: true, hideOnMobile: true, format: (v: any) => v || "—" },
			{
				key: "enable_payment_approval",
				label: "Payment approval",
				width: "minmax(120px,1fr)",
				sortable: true,
				hideOnMobile: true,
				format: (v: any) => (v ? "Yes" : "No"),
			},
			{ key: "disabled", label: "Status", width: "minmax(90px,0.8fr)", sortable: true },
		] as Column[]
	).filter((c) => readable(c.key)),
	...(can("Employee").read
		? [
				{
					key: "employees",
					label: "Active employees",
					width: "minmax(110px,0.9fr)",
					align: "right",
					format: (_: any, row: Record<string, any>) => String(employees.value[row.name] || 0),
				} as Column,
			]
		: []),
])
</script>
