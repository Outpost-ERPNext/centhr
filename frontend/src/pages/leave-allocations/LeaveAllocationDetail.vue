<template>
	<DocPageShell
		doctype="Leave Allocation"
		list-label="Leave Allocation"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="hiddenFields"
		:read-only-fields="page.doc.value.company ? [] : ['employee']"
		:link-filters="linkFilters"
		:link-queries="{ employee: 'erpnext.controllers.queries.employee_query' }"
		@change="onChange"
	>
		<template v-if="companyEditable" #before-form>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5">
				<div class="grid grid-cols-1 gap-x-5 md:grid-cols-2">
					<LinkField
						:model-value="page.doc.value.company"
						doctype="Company"
						label="Company"
						required
						@update:model-value="setCompany"
					/>
				</div>
				<p class="mt-2 text-[12.5px] text-ch-ink-3">
					{{ page.doc.value.company ? "Only this company's active employees can be selected." : "Choose a company to pick an employee." }}
				</p>
			</section>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill :status="statusLabel" />
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Balance</h3>
				<div class="text-[24px] font-semibold tabular-nums text-ch-ink">
					{{ balance === null ? "—" : formatNumber(balance) }}
					<span class="text-[13px] font-normal text-ch-ink-3">
						of {{ formatNumber(page.doc.value.total_leaves_allocated) }} days left
					</span>
				</div>
				<div class="mt-3 h-1.5 overflow-hidden rounded-full bg-ch-subtle">
					<div class="h-full rounded-full bg-ch-green-dot" :style="{ width: `${percent}%` }" />
				</div>
				<p class="mt-3 text-[12.5px] text-ch-ink-3">
					Balance on {{ formatDate(balanceDate) }}, counting all approved leave in this allocation period.
				</p>
			</section>
			<SummaryCard
				title="Allocation"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Leave type', value: page.doc.value.leave_type, route: routeFor('Leave Type', page.doc.value.leave_type) },
					{ label: 'New leaves', value: formatNumber(page.doc.value.new_leaves_allocated) },
					{ label: 'Carry forwarded', value: formatNumber(page.doc.value.unused_leaves) },
					{ label: 'Valid from', value: formatDate(page.doc.value.from_date) },
					{ label: 'Valid to', value: formatDate(page.doc.value.to_date) },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import LinkField from "@/components/fields/LinkField.vue"
import { getList } from "@/data/list"
import { useRoute } from "vue-router"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { useDocPage } from "@/data/useDocPage"
import { api } from "@/data/api"
import { formatDate, formatDateShort, formatNumber, today } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const balance = ref<number | null>(null)

const page = useDocPage("Leave Allocation", props.name, {
	defaults: () => {
		const values: Record<string, any> = {}
		if (route.query.company) values.company = route.query.company
		if (route.query.employee) values.employee = route.query.employee
		return values
	},
	onLoaded: (doc) => {
		if (page.isNew) setDefaultCompany(doc)
		loadBalance(doc)
	},
})

/** Company comes first: it is fetched from the employee on save, so here it only scopes the employee picker. */
const companyEditable = computed(() => page.editing.value && (page.isNew || page.docstatus.value === 0))
const hiddenFields = computed(() =>
	companyEditable.value ? ["naming_series", "amended_from", "company"] : ["naming_series", "amended_from"]
)

const linkFilters = {
	employee: (doc: Record<string, any>) => ({ status: "Active", ...(doc.company ? { company: doc.company } : {}) }),
	// As in the HRMS Leave Allocation form: leave without pay is never allocated
	leave_type: () => ({ is_lwp: 0 }),
}

function setCompany(company: string | null) {
	const d = page.doc.value
	if (d.company === company) return
	d.company = company
	// An employee from another company would be re-fetched over the chosen company on save
	d.employee = null
	d.employee_name = null
	d.department = null
}

/** Fills the company from a preset employee, or picks it when the user can only see one company. */
async function setDefaultCompany(doc: Record<string, any>) {
	if (doc.company) return
	const companies = doc.employee
		? (await getList({ doctype: "Employee", fields: ["company"], filters: [["name", "=", doc.employee]], limit: 1, silent: true })).map((r) => r.company)
		: (await getList({ doctype: "Company", fields: ["name"], limit: 2, silent: true })).map((r) => r.name)
	if (!page.doc.value.company && companies.length === 1 && companies[0]) page.doc.value.company = companies[0]
}

const subtitle = computed(() => {
	const d = page.doc.value
	if (page.isNew || !d.from_date) return ""
	return `${d.leave_type} · ${formatDateShort(d.from_date)} – ${formatDateShort(d.to_date)}`
})

const statusLabel = computed(() =>
	page.doc.value.docstatus === 1 && page.doc.value.expired ? "Expired" : docstatusLabel(page.docstatus.value)
)

const balanceDate = computed(() => {
	const d = page.doc.value
	const t = today()
	if (!d.from_date) return t
	return t < d.from_date ? d.from_date : t > d.to_date ? d.to_date : t
})

const percent = computed(() => {
	const total = page.doc.value.total_leaves_allocated || 0
	return total && balance.value !== null ? Math.max(0, Math.min(100, (balance.value / total) * 100)) : 0
})

async function loadBalance(doc: Record<string, any>) {
	if (page.isNew || doc.docstatus !== 1) {
		balance.value = doc.docstatus === 0 ? doc.total_leaves_allocated ?? null : null
		return
	}
	balance.value = await api<number>(
		"hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on",
		{
			employee: doc.employee,
			leave_type: doc.leave_type,
			date: balanceDate.value,
			to_date: doc.to_date,
			consider_all_leaves_in_the_allocation_period: 1,
		},
		{ silent: true }
	).catch(() => null)
}

/** The server recalculates the total on save; this keeps the form's preview in step. */
function onChange(fieldname: string) {
	const d = page.doc.value
	if (["new_leaves_allocated", "unused_leaves", "carry_forward"].includes(fieldname)) {
		d.total_leaves_allocated = (Number(d.new_leaves_allocated) || 0) + (d.carry_forward ? Number(d.unused_leaves) || 0 : 0)
	}
}
</script>
