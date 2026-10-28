<template>
	<DocPageShell
		doctype="Salary Structure Assignment"
		list-label="Salary Structure Assignment"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="hiddenFields"
		:read-only-fields="page.doc.value.company ? [] : ['employee', 'salary_structure', 'income_tax_slab', 'payroll_payable_account']"
		:link-filters="linkFilters"
		:link-queries="{ employee: 'erpnext.controllers.queries.employee_query' }"
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
					{{
						page.doc.value.company
							? "Only this company's active employees, salary structures and accounts can be selected."
							: "Choose a company to pick an employee and salary structure."
					}}
				</p>
			</section>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill :status="docstatusLabel(page.docstatus.value)" />
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Pay</h3>
				<div class="text-[24px] font-semibold tabular-nums text-ch-ink">
					{{ formatCurrency(page.doc.value.base, page.doc.value.currency) || "—" }}
					<span class="text-[13px] font-normal text-ch-ink-3">base</span>
				</div>
				<p v-if="page.doc.value.variable" class="mt-1 text-[13px] tabular-nums text-ch-ink-2">
					+ {{ formatCurrency(page.doc.value.variable, page.doc.value.currency) }} variable
				</p>
				<p class="mt-3 text-[12.5px] text-ch-ink-3">
					Applies from {{ formatDate(page.doc.value.from_date) }} until the employee's next assignment.
				</p>
			</section>
			<SummaryCard
				title="Assignment"
				:items="[
					{ label: 'Employee', value: page.doc.value.employee, route: routeFor('Employee', page.doc.value.employee) },
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Salary structure', value: page.doc.value.salary_structure },
					{ label: 'Income tax slab', value: page.doc.value.income_tax_slab },
					{ label: 'Payable account', value: page.doc.value.payroll_payable_account },
					{ label: 'From', value: formatDate(page.doc.value.from_date) },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { useRoute } from "vue-router"
import LinkField from "@/components/fields/LinkField.vue"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { getList } from "@/data/list"
import { useDocPage } from "@/data/useDocPage"
import { formatCurrency, formatDate, formatDateShort } from "@/utils/format"
import { docstatusLabel } from "@/utils/status"
import { routeFor } from "@/utils/routes"

const props = defineProps<{ name: string | null }>()
const route = useRoute()

const page = useDocPage("Salary Structure Assignment", props.name, {
	defaults: () => {
		const values: Record<string, any> = {}
		if (route.query.company) values.company = route.query.company
		if (route.query.employee) values.employee = route.query.employee
		return values
	},
	onLoaded: (doc) => {
		if (page.isNew) setDefaultCompany(doc)
	},
})

/** Company comes first: it scopes the employee, structure, tax slab and account pickers. */
const companyEditable = computed(() => page.editing.value && (page.isNew || page.docstatus.value === 0))
const hiddenFields = computed(() => (companyEditable.value ? ["amended_from", "company"] : ["amended_from"]))

// As in the HRMS Salary Structure Assignment form
const linkFilters = {
	employee: (doc: Record<string, any>) => ({ status: "Active", ...(doc.company ? { company: doc.company } : {}) }),
	salary_structure: (doc: Record<string, any>) => ({ company: doc.company, docstatus: 1, is_active: "Yes" }),
	income_tax_slab: (doc: Record<string, any>) => ({
		company: doc.company,
		docstatus: 1,
		disabled: 0,
		...(doc.currency ? { currency: doc.currency } : {}),
	}),
	payroll_payable_account: (doc: Record<string, any>) => ({ company: doc.company, root_type: "Liability", is_group: 0 }),
}

function setCompany(company: string | null) {
	const d = page.doc.value
	if (d.company === company) return
	d.company = company
	// Everything below belongs to one company, so a switch clears it
	for (const key of ["employee", "employee_name", "department", "designation", "grade", "salary_structure", "income_tax_slab", "payroll_payable_account"]) {
		d[key] = null
	}
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
	if (page.isNew || !d.salary_structure) return ""
	return `${d.salary_structure} · from ${formatDateShort(d.from_date)}`
})
</script>
