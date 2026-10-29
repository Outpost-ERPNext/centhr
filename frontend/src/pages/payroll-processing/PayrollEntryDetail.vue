<template>
	<DocPageShell
		doctype="Payroll Entry"
		list-label="Payroll Entry"
		:page="page"
		:title="period || page.doc.value.name"
		:subtitle="subtitle"
		:hidden-fields="hiddenFields"
		:link-filters="linkFilters"
		@change="onChange"
	>
		<template #actions>
			<DocActions :page="page" :allow-submit="hasEmployees">
				<Button
					v-if="canFetchEmployees"
					:variant="hasEmployees ? 'subtle' : 'solid'"
					icon-left="lucide-users"
					:label="hasEmployees ? 'Refetch employees' : 'Get employees'"
					:loading="acting === 'fetch'"
					@click="fetchEmployees"
				/>
				<Button
					v-if="canSubmitSlips"
					variant="solid"
					icon-left="lucide-send"
					label="Submit salary slips"
					:loading="acting === 'submit-slips'"
					@click="submitSlips"
				/>
				<Button
					v-if="page.doc.value.salary_slips_created && can('Salary Slip').read"
					icon-left="lucide-receipt"
					label="Salary slips"
					:route="{ name: 'SalarySlipList', query: { company: page.doc.value.company, from: page.doc.value.start_date, to: page.doc.value.end_date } }"
				/>
			</DocActions>
		</template>
		<template #status>
			<StatusBadge v-if="!page.isNew" pill doctype="Payroll Entry" :status="page.doc.value.status" />
		</template>
		<template v-if="!page.isNew && !page.editing.value" #notice>
			<div v-if="notice" class="flex items-start gap-2.5 rounded-5 border px-4 py-3 text-[13px]" :class="notice.class">
				<span class="mt-0.5 size-4 shrink-0" :class="notice.icon" />
				<div class="min-w-0 flex-1">{{ notice.text }}</div>
				<Button v-if="page.doc.value.status === 'Queued'" size="sm" label="Refresh" @click="page.reload" />
			</div>
		</template>
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
							? "Payroll runs for this company's employees. Its default currency, payable account and cost center are filled in."
							: "Choose the company to run payroll for."
					}}
				</p>
			</section>
		</template>
		<template v-if="!page.isNew && !page.editing.value" #aside>
			<section v-if="slipTotals" class="rounded-5 border border-ch-line bg-ch-surface p-4">
				<h3 class="mb-3 text-[14px] font-medium text-ch-ink">Net pay</h3>
				<div class="text-[24px] font-semibold tabular-nums text-ch-ink">
					{{ formatCurrency(slipTotals.net_pay, page.doc.value.currency) }}
				</div>
				<p class="mt-1 text-[13px] tabular-nums text-ch-ink-2">
					{{ formatCurrency(slipTotals.gross_pay, page.doc.value.currency) }} gross ·
					{{ formatCurrency(slipTotals.total_deduction, page.doc.value.currency) }} deductions
				</p>
				<p class="mt-3 text-[12.5px] text-ch-ink-3">Across {{ formatNumber(slipTotals.count) }} salary slips of this entry.</p>
			</section>
			<SummaryCard
				title="Payroll"
				:items="[
					{ label: 'Company', value: page.doc.value.company },
					{ label: 'Frequency', value: page.doc.value.payroll_frequency },
					{ label: 'Employees', value: formatNumber(page.doc.value.number_of_employees || 0) },
					{ label: 'Salary slips', value: slipStage },
					{ label: 'Payable account', value: page.doc.value.payroll_payable_account },
					{ label: 'Cost center', value: page.doc.value.cost_center },
				]"
			/>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute } from "vue-router"
import { Button, dialog, toast } from "frappe-ui"
import LinkField from "@/components/fields/LinkField.vue"
import DocActions from "@/components/DocActions.vue"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import SummaryCard from "@/components/SummaryCard.vue"
import { api, stripHtml } from "@/data/api"
import { getList } from "@/data/list"
import { cycleLabel } from "@/data/payroll"
import { runPayrollStep } from "@/data/payrollRun"
import { can } from "@/data/permissions"
import { useDocPage } from "@/data/useDocPage"
import { formatCurrency, formatDateShort, formatNumber, today } from "@/utils/format"

const props = defineProps<{ name: string | null }>()
const route = useRoute()
const acting = ref<"fetch" | "submit-slips" | null>(null)
const slipTotals = ref<{ count: number; gross_pay: number; total_deduction: number; net_pay: number } | null>(null)

const page = useDocPage("Payroll Entry", props.name, {
	defaults: () => ({
		posting_date: today(),
		payroll_frequency: "Monthly",
		...(route.query.company ? { company: route.query.company } : {}),
	}),
	onLoaded: (doc) => {
		if (page.isNew) {
			if (doc.company) setCompanyDefaults(doc.company)
			else setDefaultCompany()
			setPeriod()
		}
		loadSlipTotals(doc)
	},
})

/** Company comes first: it decides the currency, accounts and employees. */
const companyEditable = computed(() => page.editing.value && (page.isNew || page.docstatus.value === 0))
const hiddenFields = computed(() => [
	"amended_from",
	"status",
	"error_message",
	"salary_slips_created",
	"salary_slips_submitted",
	"overtime_step",
	...(companyEditable.value ? ["company", "number_of_employees"] : []),
])

// As in the HRMS Payroll Entry form
const linkFilters = {
	payroll_payable_account: (doc: Record<string, any>) => ({ company: doc.company, root_type: "Liability", is_group: 0 }),
	payment_account: (doc: Record<string, any>) => ({ company: doc.company, is_group: 0, account_type: ["in", ["Bank", "Cash"]] }),
	cost_center: (doc: Record<string, any>) => ({ company: doc.company, is_group: 0 }),
	bank_account: (doc: Record<string, any>) => ({ company: doc.company, is_company_account: 1 }),
	department: (doc: Record<string, any>) => (doc.company ? { company: doc.company } : {}),
	project: (doc: Record<string, any>) => (doc.company ? { company: doc.company } : {}),
}

const hasEmployees = computed(() => !!page.doc.value.employees?.length)
const canFetchEmployees = computed(() => !page.isNew && page.docstatus.value === 0 && page.canEdit.value)
const canSubmitSlips = computed(
	() =>
		page.docstatus.value === 1 &&
		!!page.doc.value.salary_slips_created &&
		!page.doc.value.salary_slips_submitted &&
		page.doc.value.status !== "Queued" &&
		page.permissions.value.write
)

const period = computed(() =>
	page.doc.value.start_date && page.doc.value.end_date ? cycleLabel(page.doc.value.start_date, page.doc.value.end_date) : ""
)
const subtitle = computed(() => {
	const d = page.doc.value
	if (page.isNew) return ""
	return [d.company, d.payroll_frequency, d.posting_date && `posted ${formatDateShort(d.posting_date)}`].filter(Boolean).join(" · ")
})
const slipStage = computed(() => {
	const d = page.doc.value
	if (d.salary_slips_submitted) return "Submitted"
	if (d.salary_slips_created) return "Created, not submitted"
	return d.docstatus === 1 ? "Not created" : "Created on submit"
})

const notice = computed(() => {
	const d = page.doc.value
	if (d.status === "Queued")
		return {
			text: "Salary slips are being processed in the background. Refresh in a moment to see the result.",
			icon: "lucide-loader",
			class: "border-ch-line bg-ch-amber-bg text-ch-amber-ink",
		}
	if (d.status === "Failed" && d.error_message)
		return { text: stripHtml(d.error_message), icon: "lucide-circle-alert", class: "border-ch-line bg-ch-red-bg text-ch-red-ink" }
	if (d.docstatus === 0 && !hasEmployees.value)
		return {
			text: "Get employees to list everyone this payroll covers. Submitting the entry then creates their salary slips.",
			icon: "lucide-info",
			class: "border-ch-line bg-ch-surface text-ch-ink-2",
		}
	if (d.docstatus === 0)
		return {
			text: `${formatNumber(d.employees.length)} employees fetched. Submit the entry to create their draft salary slips.`,
			icon: "lucide-info",
			class: "border-ch-line bg-ch-surface text-ch-ink-2",
		}
	if (canSubmitSlips.value)
		return {
			text: "Salary slips are created as drafts. Review them, then submit them to book the payroll accrual.",
			icon: "lucide-info",
			class: "border-ch-line bg-ch-surface text-ch-ink-2",
		}
	return null
})

/** Changing who or when the payroll covers makes the fetched employee list stale. */
function clearEmployees() {
	page.doc.value.employees = []
	page.doc.value.number_of_employees = 0
}

function setCompany(company: string | null) {
	const d = page.doc.value
	if (d.company === company) return
	d.company = company
	for (const key of ["payroll_payable_account", "cost_center", "payment_account", "bank_account", "department", "project"]) d[key] = null
	clearEmployees()
	if (company) setCompanyDefaults(company)
}

async function setCompanyDefaults(company: string) {
	const [row] = await getList({
		doctype: "Company",
		fields: ["default_currency", "default_payroll_payable_account", "cost_center"],
		filters: [["name", "=", company]],
		limit: 1,
		silent: true,
	}).catch(() => [])
	const d = page.doc.value
	if (!row || d.company !== company) return
	d.currency = row.default_currency
	d.exchange_rate = 1
	if (!d.payroll_payable_account) d.payroll_payable_account = row.default_payroll_payable_account
	if (!d.cost_center) d.cost_center = row.cost_center
}

/** Picks the company when the user can only see one. */
async function setDefaultCompany() {
	const companies = await getList({ doctype: "Company", fields: ["name"], limit: 2, silent: true }).catch(() => [])
	if (!page.doc.value.company && companies.length === 1) setCompany(companies[0].name)
}

/** The pay period around the posting date for the chosen frequency. */
async function setPeriod() {
	const d = page.doc.value
	if (!d.payroll_frequency) return
	const dates = await api<{ start_date: string; end_date: string }>(
		"hrms.payroll.doctype.payroll_entry.payroll_entry.get_start_end_dates",
		{ payroll_frequency: d.payroll_frequency, start_date: d.posting_date || today() },
		{ silent: true }
	).catch(() => null)
	if (dates) {
		d.start_date = dates.start_date
		d.end_date = dates.end_date
	}
}

async function setEndDate() {
	const d = page.doc.value
	if (!d.start_date) return
	const dates = await api<{ end_date: string }>(
		"hrms.payroll.doctype.payroll_entry.payroll_entry.get_end_date",
		{ start_date: d.start_date, frequency: d.payroll_frequency },
		{ silent: true }
	).catch(() => null)
	if (dates?.end_date) d.end_date = dates.end_date
}

function onChange(fieldname: string) {
	if (fieldname === "payroll_frequency") setPeriod()
	if (fieldname === "start_date") setEndDate()
	if (["payroll_frequency", "start_date", "end_date", "branch", "department", "designation", "grade", "project", "currency", "payroll_payable_account"].includes(fieldname)) {
		clearEmployees()
	}
}

async function fetchEmployees() {
	acting.value = "fetch"
	try {
		const unmarked = await api<any[] | null>("centhr.api.payroll.fill_payroll_employees", { payroll_entry: page.doc.value.name })
		await page.reload()
		toast.success(`${formatNumber(page.doc.value.employees?.length || 0)} employees fetched`)
		if (unmarked?.length) toast.warning(`${formatNumber(unmarked.length)} employees have unmarked attendance in this period`)
	} catch {
		// The api helper already showed the server's message
	} finally {
		acting.value = null
	}
}

function submitSlips() {
	dialog.confirm({
		title: "Submit salary slips",
		message: `Submit all draft salary slips of ${period.value}? This books the payroll accrual and the slips can no longer be edited.`,
		confirmLabel: "Submit",
		onConfirm: async () => {
			acting.value = "submit-slips"
			try {
				await runPayrollStep(page.doc.value.name, "submit_slips")
				toast.success("Salary slips submitted")
				await page.reload()
			} finally {
				acting.value = null
			}
		},
	})
}

async function loadSlipTotals(doc: Record<string, any>) {
	slipTotals.value = null
	if (page.isNew || !doc.salary_slips_created || !can("Salary Slip").read) return
	const [row] = await getList({
		doctype: "Salary Slip",
		fields: [
			{ COUNT: "*", as: "count" },
			{ SUM: "gross_pay", as: "gross_pay" },
			{ SUM: "total_deduction", as: "total_deduction" },
			{ SUM: "net_pay", as: "net_pay" },
		],
		filters: [
			["payroll_entry", "=", doc.name],
			["docstatus", "!=", 2],
		],
		limit: 1,
		silent: true,
	}).catch(() => [])
	slipTotals.value = row?.count ? (row as any) : null
}
</script>
