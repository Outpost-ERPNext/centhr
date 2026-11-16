<template>
	<PageHeader :crumbs="[{ label: 'Peer Mapping' }]">
		<template #actions>
			<template v-if="can('PMS Employee Relationship').write">
				<Button icon-left="lucide-refresh-cw" label="Run peer mapping" @click="runOpen = true" />
				<Button variant="solid" icon-left="lucide-plus" label="New mapping" :route="{ name: 'PmsRelationshipNew' }" />
			</template>
		</template>
	</PageHeader>

	<FilterBar
		v-model:search="list.state.search"
		:total="list.total.value"
		:active="hasFilters"
		search-placeholder="Search employees"
		noun="employee"
		@clear="list.clearFilters"
	>
		<FilterLink v-model="list.state.filters.company" doctype="Company" placeholder="Company" />
		<FilterLink v-model="list.state.filters.department" doctype="Department" placeholder="Department" :filters="{ is_group: 0 }" />
		<FilterSelect
			v-model="list.state.filters.locked"
			:options="[
				{ label: 'Locked', value: '1' },
				{ label: 'Not locked', value: '0' },
			]"
			placeholder="Lock"
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
		empty-icon="lucide-users"
		:empty-message="hasFilters ? 'No mappings match these filters' : 'No peer mappings yet. Run peer mapping to create them.'"
		mobile-aside="locked"
		@sort="list.toggleSort"
		@row-click="(row) => router.push(routeFor('PMS Employee Relationship', row.name)!)"
		@clear-filters="list.clearFilters"
	>
		<template #cell-employee_name="{ row }">
			<div class="min-w-0">
				<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
				<div class="truncate text-[12px] text-ch-ink-3">{{ [row.employee, row.grade].filter(Boolean).join(" · ") }}</div>
			</div>
		</template>
		<template #cell-locked="{ row }">
			<StatusBadge v-if="row.locked" tone="amber" status="Locked" />
		</template>
	</DataTable>

	<Pager v-model:page="list.state.page" v-model:page-size="list.state.pageSize" :total="list.total.value" />

	<Dialog v-model:open="runOpen" title="Run peer mapping">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Gives every active employee of the company who has a department up to 2 peers: first colleagues of the same department, grade
				and line manager, then the same department and grade, then one grade lower. Peers who left are replaced. Locked mappings are
				not changed. This also runs by itself on the 1st and 16th.
			</p>
			<LinkField v-model="runCompany" doctype="Company" label="Company" required size="md" />
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="runOpen = false" />
				<Button variant="solid" label="Run" :disabled="!runCompany" :loading="running" @click="run" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button, Dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import LinkField from "@/components/fields/LinkField.vue"
import Pager from "@/components/Pager.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useDocList, type Filter } from "@/data/list"
import { can } from "@/data/permissions"
import { runPeerMapping } from "@/data/pms"
import { routeFor } from "@/utils/routes"

const router = useRouter()

const list = useDocList({
	doctype: "PMS Employee Relationship",
	fields: ["name", "employee", "employee_name", "company", "department", "grade", "line_manager_name", "peer_names", "locked"],
	searchFields: ["employee_name", "employee"],
	defaultSort: { field: "employee_name", order: "asc" },
	buildFilters: (state) => {
		const filters: Filter[] = []
		for (const field of ["company", "department"]) {
			if (state.filters[field]) filters.push([field, "=", state.filters[field]])
		}
		if (state.filters.locked) filters.push(["locked", "=", Number(state.filters.locked)])
		return filters
	},
})

const hasFilters = computed(() => !!list.state.search || Object.values(list.state.filters).some(Boolean))

const runOpen = ref(false)
const runCompany = ref<string | null>(null)
const running = ref(false)

async function run() {
	running.value = true
	try {
		const stats = await runPeerMapping(runCompany.value!)
		runOpen.value = false
		toast.success(
			`${stats.employees} employees checked: ${stats.created} mappings created, ${stats.peers_added} peers added, ${stats.peers_removed} removed, ${stats.locked} locked and left alone`
		)
		list.reload()
	} finally {
		running.value = false
	}
}

const columns: Column[] = [
	{ key: "employee_name", label: "Employee", width: "minmax(220px,1.8fr)", sortable: true },
	{ key: "department", label: "Department", width: "minmax(140px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "line_manager_name", label: "Line manager", width: "minmax(150px,1.2fr)", hideOnMobile: true, format: (v) => v || "—" },
	{ key: "peer_names", label: "Peers", width: "minmax(200px,2fr)", format: (v) => v || "No peers" },
	{ key: "locked", label: "", width: "90px" },
]
</script>
