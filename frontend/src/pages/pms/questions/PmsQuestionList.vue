<template>
	<PageHeader :crumbs="[{ label: 'PMS Question Bank' }]">
		<template #actions>
			<Button v-if="can('PMS Question').create" variant="solid" icon-left="lucide-plus" label="New question" :route="{ name: 'PmsQuestionNew' }" />
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search questions"
		noun="question"
		@clear="list.clearFilters"
	>
		<FilterSelect
			v-model="list.state.filters.general"
			:options="[
				{ label: 'General', value: '1' },
				{ label: 'Department or designation', value: '0' },
			]"
			placeholder="Asked for"
		/>
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" />
		<FilterLink v-model="list.state.filters.designation" doctype="Designation" placeholder="Designation" />
	</FilterBar>

	<DataTable
		:columns="columns"
		:rows="list.rows.value"
		:loading="list.loading.value"
		:error="list.error.value"
		:sort-field="list.state.sortField"
		:sort-order="list.state.sortOrder"
		:show-clear="hasFilters"
		empty-icon="lucide-list-checks"
		:empty-message="hasFilters ? 'No questions match these filters' : 'No questions in the bank yet'"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('PMS Question', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-question="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.question }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ row.name }}</div>
			</div>
		</template>
		<template #cell-is_a_general_question="{ row }">
			<StatusBadge v-if="row.is_a_general_question" tone="blue" status="Everyone" />
			<span v-else class="truncate">{{ [row.department, row.designation].filter(Boolean).join(" · ") || "—" }}</span>
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "PMS Question",
	fields: ["name", "question", "question_head", "is_a_general_question", "department", "designation"],
	searchFields: ["question", "name"],
	defaultSort: { field: "creation", order: "desc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		if (state.filters.general) filters.push(["is_a_general_question", "=", Number(state.filters.general)])
		if (state.filters.department) filters.push(["department", "=", state.filters.department])
		if (state.filters.designation) filters.push(["designation", "=", state.filters.designation])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const columns: Column[] = [
	{ key: "question", label: "Question", width: "minmax(280px,3fr)" },
	{ key: "is_a_general_question", label: "Asked for", width: "minmax(200px,1.6fr)" },
	{ key: "question_head", label: "Head", width: "110px", hideOnMobile: true },
]
</script>
