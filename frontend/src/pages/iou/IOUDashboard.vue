<template>
	<div class="flex h-full flex-col overflow-hidden bg-ch-bg">
		<!-- Page Header with Breadcrumbs & Actions -->
		<PageHeader :crumbs="[{ label: 'IOU' }, { label: 'IOU Dashboard' }]">
			<template #actions>
				<div class="flex items-center gap-2">
					<Button
						variant="ghost"
						size="sm"
						icon-left="lucide-rotate-ccw"
						label="Refresh"
						:loading="loading"
						@click="loadData"
					/>
					<Dropdown :options="reportOptions">
						<Button size="sm" variant="ghost" icon-left="lucide-chart-column" label="Reports" />
					</Dropdown>
					<Button
						size="sm"
						icon-left="lucide-file-spreadsheet"
						label="Export"
						:loading="exporting"
						:disabled="!rows.length"
						@click="exportExcel"
					/>
				</div>
			</template>
		</PageHeader>

		<!-- Main Scrollable Area -->
		<div class="min-h-0 flex-1 overflow-y-auto">
			<!-- Advance, approval and overdue totals; each card shows only its rows -->
			<div class="grid grid-cols-1 gap-3 px-5 pt-4 sm:grid-cols-2 lg:grid-cols-4">
				<StatCard
					v-for="card in focusCards"
					:key="card.focus"
					:label="card.label"
					:value="formatCurrency(card.stat.amount)"
					:sub="card.sub"
					:tone="card.tone"
					clickable
					:active="selectedFocus === card.focus"
					:loading="loading"
					@click="toggleFocus(card.focus)"
				/>
			</div>

			<!-- Three Colored Category Metric Cards -->
			<div class="grid grid-cols-1 gap-3 px-5 pt-3 sm:grid-cols-3">
				<!-- Category 1: IOU Application (Blue) -->
				<StatCard
					label="IOU Application"
					:value="formatCurrency(stats.iou_application.amount)"
					:sub="`${stats.iou_application.count} applications`"
					tone="blue"
					clickable
					:active="selectedCategory === 'IOU Application'"
					:loading="loading"
					@click="toggleCategory('IOU Application')"
				/>

				<!-- Category 2: IOU Claim Settlement – No Linked IOU (Amber) -->
				<StatCard
					label="Claim Settlement · No Linked IOU"
					:value="formatCurrency(stats.settlement_no_link.amount)"
					:sub="`${stats.settlement_no_link.count} settlements (Direct)`"
					tone="amber"
					clickable
					:active="selectedCategory === 'IOU Claim Settlement – No Linked IOU'"
					:loading="loading"
					@click="toggleCategory('IOU Claim Settlement – No Linked IOU')"
				/>

				<!-- Category 3: IOU Claim Settlement – Linked IOU (Green) -->
				<StatCard
					label="Claim Settlement · Linked IOU"
					:value="formatCurrency(stats.settlement_linked.amount)"
					:sub="`${stats.settlement_linked.count} settlements (Linked)`"
					tone="green"
					clickable
					:active="selectedCategory === 'IOU Claim Settlement – Linked IOU'"
					:loading="loading"
					@click="toggleCategory('IOU Claim Settlement – Linked IOU')"
				/>
			</div>

			<!-- Active Card Filter Indicators -->
			<div
				v-if="selectedCategory || selectedFocus"
				class="flex flex-wrap items-center gap-2 px-5 pt-2 text-[12.5px] text-ch-ink-2"
			>
				<span>Showing:</span>
				<span
					v-if="activeFocusCard"
					class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-medium"
					:class="`bg-ch-${activeFocusCard.tone}-bg text-ch-${activeFocusCard.tone}-ink`"
				>
					{{ activeFocusCard.label }}
					<button type="button" class="hover:opacity-75" aria-label="Remove card filter" @click="selectedFocus = ''">
						✕
					</button>
				</span>
				<span
					v-if="selectedCategory"
					class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-medium"
					:class="categoryBadgeClass(selectedCategory)"
				>
					{{ selectedCategory }}
					<button
						type="button"
						class="hover:opacity-75"
						aria-label="Remove category filter"
						@click="selectedCategory = ''"
					>
						✕
					</button>
				</span>
			</div>

			<!-- Filter Bar -->
			<FilterBar
				v-model:search="searchQuery"
				:total="rows.length"
				:active="hasActiveFilters"
				search-placeholder="Search employee, reference, purpose…"
				noun="transaction"
				@clear="clearFilters"
			>
				<!-- Company Link Filter -->
				<FilterLink v-model="selectedCompany" doctype="Company" placeholder="Company" />

				<!-- Employee Link Filter -->
				<FilterLink
					v-model="selectedEmployee"
					doctype="Employee"
					placeholder="Employee"
					:filters="selectedCompany ? { company: selectedCompany } : undefined"
				/>

				<!-- Advance Type Filter -->
				<FilterSelect
					v-model="selectedAdvanceType"
					:options="advanceTypes"
					placeholder="Advance Type"
				/>

				<!-- Status Filter -->
				<FilterSelect
					v-model="selectedStatus"
					:options="statuses"
					placeholder="Status"
				/>

				<!-- Closed Transactions Checkbox -->
				<label class="flex cursor-pointer select-none items-center gap-2 rounded-3 px-2 py-1 text-[13px] text-ch-ink hover:bg-ch-subtle">
					<Checkbox v-model="showClosed" />
					<span class="whitespace-nowrap">Closed Transactions</span>
				</label>
			</FilterBar>

			<!-- DataTable -->
			<div class="px-5 pb-8">
				<DataTable
					:columns="columns"
					:rows="rows"
					:loading="loading"
					:error="error"
					row-key="name"
					clickable
					empty-icon="lucide-receipt"
					empty-message="No IOU transactions match the selected filters"
					min-width="1160px"
					@row-click="openDetail"
				>
					<!-- Category Column -->
					<template #cell-category="{ row }">
						<span
							class="inline-block rounded-full px-2.5 py-0.5 text-[11px] font-medium"
							:class="categoryBadgeClass(row.category)"
						>
							{{ shortCategory(row.category) }}
						</span>
					</template>

					<!-- Reference No Column -->
					<template #cell-name="{ row }">
						<div class="min-w-0">
							<div class="flex items-center gap-1 font-medium text-ch-ink">
								<span class="truncate">{{ row.name }}</span>
								<button
									type="button"
									class="text-ch-ink-4 hover:text-ch-ink"
									title="Open in Desk"
									@click.stop="openDesk(row.doctype, row.name)"
								>
									<span class="lucide-external-link size-3" />
								</button>
							</div>
							<div v-if="row.employee_advance && row.employee_advance !== row.name" class="truncate text-[11px] text-ch-ink-3">
								Linked: {{ row.employee_advance }}
							</div>
							<div v-if="row.linked_iou" class="truncate text-[11px] text-ch-ink-3">
								Linked IOU: {{ row.linked_iou }}
							</div>
						</div>
					</template>

					<!-- Advance Type Column -->
					<template #cell-advance_type="{ row }">
						<span class="truncate text-ch-ink" :title="row.advance_type">
							{{ row.advance_type ? shortCategory(row.advance_type) : "—" }}
						</span>
					</template>

					<!-- Employee Column -->
					<template #cell-employee="{ row }">
						<div class="min-w-0">
							<div class="truncate font-medium text-ch-ink">{{ row.employee_name }}</div>
							<div class="truncate text-[11.5px] text-ch-ink-3">{{ row.employee }}</div>
						</div>
					</template>

					<!-- Amount Column -->
					<template #cell-amount="{ row }">
						<div class="text-right">
							<div class="font-medium text-ch-ink tabular-nums">{{ formatCurrency(row.amount) }}</div>
							<!-- SOP: the part settling the IOU (yellow) and the part paid to the employee (blue) -->
							<div v-if="row.doctype === 'Expense Claim' && row.amount_from_iou" class="text-[11px] tabular-nums">
								<span class="text-ch-amber-ink" title="Settled from IOU">IOU {{ formatCurrency(row.amount_from_iou) }}</span>
								<span v-if="row.amount_from_pocket" class="text-ch-blue-ink" title="Paid to the employee">
									· Pocket {{ formatCurrency(row.amount_from_pocket) }}
								</span>
							</div>
							<div
								v-else-if="row.outstanding_amount && row.outstanding_amount !== row.amount"
								class="text-[11px] text-ch-ink-3 tabular-nums"
							>
								Bal: {{ formatCurrency(row.outstanding_amount) }}
							</div>
						</div>
					</template>

					<!-- Application Date Column -->
					<template #cell-posting_date="{ row }">
						<span class="text-ch-ink">{{ formatDateShort(row.posting_date) }}</span>
					</template>

					<!-- Due Date Column -->
					<template #cell-due_date="{ row }">
						<div class="flex items-center gap-1.5">
							<span :class="row.is_overdue ? 'font-medium text-ch-red-ink' : 'text-ch-ink'">
								{{ row.due_date ? formatDateShort(row.due_date) : "—" }}
							</span>
							<span
								v-if="row.is_overdue"
								class="rounded bg-ch-red-bg px-1 py-0.2 text-[10px] font-semibold text-ch-red-ink"
							>
								Due
							</span>
						</div>
					</template>

					<!-- Approvers Column (HOD, Finance 1, Finance 2): green tick approved, red cross rejected -->
					<template #cell-approvers="{ row }">
						<div class="flex items-center gap-1.5">
							<div
								v-for="stage in APPROVER_STAGES"
								:key="stage.key"
								class="flex size-6 items-center justify-center rounded-full text-[10px] font-semibold"
								:class="approverBadgeStyle(row.approvers?.[stage.key]?.status)"
								:title="approverTitle(stage.label, row.approvers?.[stage.key])"
							>
								<span v-if="row.approvers?.[stage.key]?.status === 'Approved'" class="lucide-check size-3.5" />
								<span v-else-if="row.approvers?.[stage.key]?.status === 'Rejected'" class="lucide-x size-3.5" />
								<template v-else>{{ stage.short }}</template>
							</div>
						</div>
					</template>

					<!-- Status Column -->
					<template #cell-status="{ row }">
						<StatusBadge :doctype="row.doctype" :status="row.status" pill />
					</template>

					<!-- Actions Column -->
					<template #cell-actions="{ row }">
						<div class="flex items-center justify-end gap-1" @click.stop>
							<Button
								v-for="action in primaryActions(row as IOURow)"
								:key="action"
								size="sm"
								variant="solid"
								:label="action"
								@click="startAction(row as IOURow, action)"
							/>
							<Dropdown v-if="secondaryActions(row as IOURow).length" :options="dropdownOptions(row as IOURow)">
								<Button size="sm" variant="ghost" icon="lucide-more-horizontal" aria-label="More actions" />
							</Dropdown>
							<Button
								v-else
								size="sm"
								variant="ghost"
								label="View"
								@click="openDetail(row as IOURow)"
							/>
							<Button
								size="sm"
								variant="ghost"
								icon="lucide-external-link"
								aria-label="Open in Desk"
								@click="openDesk(row.doctype, row.name)"
							/>
						</div>
					</template>
				</DataTable>
			</div>
		</div>

		<!-- Detail Dialog / Modal -->
		<IOUDetailDialog
			v-model="detailOpen"
			:row="selectedRow"
			@action="(action) => selectedRow && startAction(selectedRow, action)"
		/>

		<!-- Approve / Reject / Modify / Pay -->
		<IOUActionDialog v-model="actionOpen" :row="actionRow" :action="pendingAction" @done="loadData" />
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue"
import { Button, Checkbox, Dropdown, toast } from "frappe-ui"
import DataTable, { type Column } from "@/components/DataTable.vue"
import FilterBar from "@/components/FilterBar.vue"
import FilterLink from "@/components/FilterLink.vue"
import FilterSelect from "@/components/FilterSelect.vue"
import PageHeader from "@/components/layout/PageHeader.vue"
import StatCard from "@/components/StatCard.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import {
	exportIOURecords,
	getIOUDashboard,
	type IOUAction,
	type IOUApproverInfo,
	type IOUCategory,
	type IOUFocus,
	type IOURow,
	type IOUStats,
} from "@/data/iou"
import { formatCurrency, formatDateShort } from "@/utils/format"
import IOUActionDialog from "./IOUActionDialog.vue"
import IOUDetailDialog from "./IOUDetailDialog.vue"

// State
const loading = ref(false)
const exporting = ref(false)
const error = ref<string | null>(null)
const rows = ref<IOURow[]>([])
const advanceTypes = ref<string[]>([])
const statuses = ref<string[]>([])

const stats = ref<IOUStats>({
	iou_application: { count: 0, amount: 0 },
	settlement_no_link: { count: 0, amount: 0 },
	settlement_linked: { count: 0, amount: 0 },
	total: { count: 0, amount: 0 },
	advances: { count: 0, amount: 0 },
	pending_approval: { count: 0, amount: 0 },
	overdue: { count: 0, amount: 0 },
	waiting_for_me: { count: 0, amount: 0 },
})

const focusCards = computed(() => [
	{
		focus: "mine" as IOUFocus,
		label: "Waiting for Me",
		stat: stats.value.waiting_for_me,
		sub: `${stats.value.waiting_for_me.count} to approve or pay`,
		tone: "green" as const,
	},
	{
		focus: "advances" as IOUFocus,
		label: "Total Advances",
		stat: stats.value.advances,
		sub: `${stats.value.advances.count} employee advances`,
		tone: "blue" as const,
	},
	{
		focus: "pending" as IOUFocus,
		label: "Pending Approval",
		stat: stats.value.pending_approval,
		sub: `${stats.value.pending_approval.count} awaiting an approver`,
		tone: "amber" as const,
	},
	{
		focus: "overdue" as IOUFocus,
		label: "Overdue",
		stat: stats.value.overdue,
		sub: `${stats.value.overdue.count} past the due date`,
		tone: "red" as const,
	},
])
const activeFocusCard = computed(() => focusCards.value.find((card) => card.focus === selectedFocus.value))

// Filters
const searchQuery = ref("")
const selectedCompany = ref("")
const selectedEmployee = ref("")
const selectedAdvanceType = ref("")
const selectedStatus = ref("")
const selectedCategory = ref<string>("")
const selectedFocus = ref<IOUFocus | "">("")
const showClosed = ref(false)

// Detail modal
const detailOpen = ref(false)
const selectedRow = ref<IOURow | null>(null)

// Table column definitions
const columns: Column[] = [
	{ key: "category", label: "Category", width: "160px" },
	{ key: "name", label: "Reference No", width: "minmax(130px, 1.2fr)", sortable: true },
	{ key: "advance_type", label: "Advance Type", width: "130px", sortable: true },
	{ key: "employee", label: "Employee", width: "minmax(160px, 1.4fr)", sortable: true },
	{ key: "amount", label: "Amount", width: "130px", align: "right", sortable: true },
	{ key: "posting_date", label: "Application Date", width: "125px", sortable: true },
	{ key: "due_date", label: "Due Date", width: "120px", sortable: true },
	{ key: "approvers", label: "Approvers", width: "105px" },
	{ key: "status", label: "Status", width: "130px", sortable: true },
	{ key: "actions", label: "Actions", width: "150px", align: "right" },
]

const hasActiveFilters = computed(() => {
	return Boolean(
		searchQuery.value ||
			selectedCompany.value ||
			selectedEmployee.value ||
			selectedAdvanceType.value ||
			selectedStatus.value ||
			selectedCategory.value ||
			selectedFocus.value ||
			showClosed.value
	)
})

async function loadData() {
	loading.value = true
	error.value = null
	try {
		const res = await getIOUDashboard({
			company: selectedCompany.value || undefined,
			employee: selectedEmployee.value || undefined,
			advance_type: selectedAdvanceType.value || undefined,
			status: selectedStatus.value || undefined,
			category: selectedCategory.value || undefined,
			focus: selectedFocus.value || undefined,
			search: searchQuery.value || undefined,
			closed: showClosed.value ? 1 : 0,
		})
		rows.value = res.records || []
		stats.value = res.stats || stats.value
		advanceTypes.value = res.advance_types || []
		statuses.value = res.statuses || []
	} catch (err: any) {
		error.value = err?.message || "Failed to load IOU dashboard data"
	} finally {
		loading.value = false
	}
}

// Watch filters to reload data
let debounceTimer: any = null
watch([selectedCompany, selectedEmployee, selectedAdvanceType, selectedStatus, selectedCategory, selectedFocus, showClosed], () => {
	loadData()
})

watch(searchQuery, () => {
	clearTimeout(debounceTimer)
	debounceTimer = setTimeout(() => {
		loadData()
	}, 250)
})

function toggleCategory(cat: IOUCategory) {
	if (selectedCategory.value === cat) {
		selectedCategory.value = ""
	} else {
		selectedCategory.value = cat
	}
}

function toggleFocus(focus: IOUFocus) {
	selectedFocus.value = selectedFocus.value === focus ? "" : focus
}

function clearFilters() {
	searchQuery.value = ""
	selectedCompany.value = ""
	selectedEmployee.value = ""
	selectedAdvanceType.value = ""
	selectedStatus.value = ""
	selectedCategory.value = ""
	selectedFocus.value = ""
	showClosed.value = false
}

function openDetail(row: Record<string, any>) {
	selectedRow.value = row as IOURow
	detailOpen.value = true
}

// Action dialog
const actionOpen = ref(false)
const actionRow = ref<IOURow | null>(null)
const pendingAction = ref<IOUAction | null>(null)

const APPROVER_STAGES = [
	{ key: "hod", label: "HOD", short: "H" },
	{ key: "finance_1", label: "Finance 1", short: "F1" },
	{ key: "finance_2", label: "Finance 2", short: "F2" },
] as const

// SOP: IOU Reporting (open in Desk)
const reportOptions = ["IOU Advance Summary", "IOU Advance Report"].map((report) => ({
	label: report,
	icon: "lucide-file-chart-column",
	onClick: () => window.open(`/desk/query-report/${encodeURIComponent(report)}`, "_blank"),
}))

// Approve and Pay are one click away; Reject and Modify sit in the menu
const PRIMARY: IOUAction[] = ["Approve", "Pay"]

function primaryActions(row: IOURow) {
	return (row.actions || []).filter((action) => PRIMARY.includes(action))
}

function secondaryActions(row: IOURow) {
	return (row.actions || []).filter((action) => !PRIMARY.includes(action))
}

function dropdownOptions(row: IOURow) {
	return [
		...secondaryActions(row).map((action) => ({
			label: action,
			icon: action === "Reject" ? "lucide-x" : "lucide-pencil",
			onClick: () => startAction(row, action),
		})),
		{ label: "View", icon: "lucide-eye", onClick: () => openDetail(row) },
	]
}

function startAction(row: IOURow, action: IOUAction) {
	detailOpen.value = false
	actionRow.value = row
	pendingAction.value = action
	actionOpen.value = true
}

function approverTitle(label: string, approver?: IOUApproverInfo) {
	const who = approver?.name || approver?.user
	const reason = approver?.reason ? ` – ${approver.reason}` : ""
	return `${label}${who ? ` (${who})` : ""}: ${approver?.status || "Pending"}${reason}`
}

function openDesk(doctype: string, name: string) {
	const slug = doctype.toLowerCase().replace(/ /g, "-")
	window.open(`/desk/${slug}/${encodeURIComponent(name)}`, "_blank")
}

async function exportExcel() {
	if (!rows.value.length) return
	exporting.value = true
	try {
		await exportIOURecords(
			{
				company: selectedCompany.value || undefined,
				employee: selectedEmployee.value || undefined,
				advance_type: selectedAdvanceType.value || undefined,
				status: selectedStatus.value || undefined,
				category: selectedCategory.value || undefined,
				focus: selectedFocus.value || undefined,
				search: searchQuery.value || undefined,
				closed: showClosed.value ? 1 : 0,
			},
			rows.value.map((r) => r.name)
		)
	} catch {
		toast.error("Failed to export IOU records")
	} finally {
		exporting.value = false
	}
}

function shortCategory(cat: string) {
	if (cat === "IOU Application") return "Application"
	if (cat === "IOU Claim Settlement – No Linked IOU") return "Claim (No Link)"
	if (cat === "IOU Claim Settlement – Linked IOU") return "Claim (Linked)"
	return cat
}

function categoryBadgeClass(cat: string) {
	if (cat === "IOU Application") return "bg-ch-blue-bg text-ch-blue-ink"
	if (cat === "IOU Claim Settlement – No Linked IOU") return "bg-ch-amber-bg text-ch-amber-ink"
	return "bg-ch-green-bg text-ch-green-ink"
}

function approverBadgeStyle(status: string | undefined): string {
	if (status === "Approved") return "bg-ch-green-bg text-ch-green-ink"
	if (status === "Rejected") return "bg-ch-red-bg text-ch-red-ink"
	if (status === "Pending") return "bg-ch-amber-bg text-ch-amber-ink"
	return "bg-ch-subtle text-ch-ink-4"
}

onMounted(() => {
	loadData()
})
</script>
