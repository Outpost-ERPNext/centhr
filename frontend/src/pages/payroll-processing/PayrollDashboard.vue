<template>
	<PageHeader :crumbs="[{ label: 'Payroll Dashboard' }]">
		<template #actions>
			<Button
				icon-left="lucide-settings"
				label="Payroll settings"
				:tooltip="state.company ? undefined : 'Choose a company to see its pay cycle settings'"
				:disabled="!state.company"
				@click="settingsOpen = true"
			/>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" @click="refresh" />
		</template>
	</PageHeader>

	<!-- One scroll area: every tab has cards and filters above its table -->
	<div class="min-h-0 flex-1 overflow-y-auto">
		<div class="flex flex-wrap items-center gap-2 px-5 pt-3">
			<div class="w-56">
				<FilterLink v-model="state.company" doctype="Company" placeholder="All companies" />
			</div>
			<PayrollCycleNav :key="cycleKey" show-rule :company="state.company" :from="state.from" :to="state.to" @update:from="state.from = $event" @update:to="state.to = $event" />
			<span v-if="state.from" class="rounded-full bg-ch-subtle px-3 py-1 text-[12px] text-ch-ink-3">
				Cycle <b class="tabular-nums text-ch-ink">{{ formatDateShort(state.from) }} → {{ formatDateShort(state.to) }}</b>
			</span>
		</div>

		<nav class="sticky top-0 z-[2] mt-2 flex gap-1 overflow-x-auto border-b border-ch-line bg-ch-bg px-5" role="tablist" aria-label="Payroll dashboard">
			<button
				v-for="t in TABS"
				:key="t.key"
				type="button"
				role="tab"
				:aria-selected="tab === t.key"
				class="-mb-px flex h-11 shrink-0 items-center gap-1.5 border-b-2 px-2 text-[13.5px]"
				:class="tab === t.key ? 'border-ch-primary font-medium text-ch-ink' : 'border-transparent text-ch-ink-3 hover:text-ch-ink'"
				@click="tab = t.key"
			>
				{{ t.label }}
				<span v-if="badges[t.key]" class="rounded-full bg-ch-subtle px-1.5 text-[11.5px] tabular-nums text-ch-ink-2">{{ badges[t.key] }}</span>
			</button>
		</nav>

		<KeepAlive>
			<component :is="TAB_COMPONENTS[tab]" :key="`${tab}-${refreshKey}`" v-bind="tabProps" />
		</KeepAlive>
	</div>

	<EmployeeQuickView :employee="quickView" :from="state.from" :to="state.to" @close="quickView = null" />
	<PayrollSettingsDialog v-if="state.company" v-model:open="settingsOpen" :company="state.company" @saved="onSettingsSaved" />
</template>

<script setup lang="ts">
import { computed, provide, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import EmployeeQuickView from "@/components/EmployeeQuickView.vue"
import FilterLink from "@/components/FilterLink.vue"
import PayrollCycleNav from "@/components/PayrollCycleNav.vue"
import AuditTab from "./dashboard/AuditTab.vue"
import EmployeesTab from "./dashboard/EmployeesTab.vue"
import AttendanceTab from "./dashboard/AttendanceTab.vue"
import ProcessingTab from "./dashboard/ProcessingTab.vue"
import AnalyticsTab from "./dashboard/AnalyticsTab.vue"
import AdvancesTab from "./dashboard/AdvancesTab.vue"
import ReportsTab from "./dashboard/ReportsTab.vue"
import ComplianceTab from "./dashboard/ComplianceTab.vue"
import PayrollSettingsDialog from "./PayrollSettingsDialog.vue"
import { OPEN_EMPLOYEE, TABS, type TabKey } from "@/data/payrollDashboard"
import { useSalaryOverview } from "@/data/useSalaryOverview"
import { formatDateShort } from "@/utils/format"

const TAB_COMPONENTS: Record<TabKey, any> = {
	audit: AuditTab,
	employees: EmployeesTab,
	attendance: AttendanceTab,
	processing: ProcessingTab,
	analytics: AnalyticsTab,
	advances: AdvancesTab,
	reports: ReportsTab,
	compliance: ComplianceTab,
}

const route = useRoute()
const router = useRouter()
// Company, cycle and the Employees tab's filters; the tabs all read company and cycle from here
const overview = useSalaryOverview("payroll")
const { state, rows } = overview

const tab = ref<TabKey>(TABS.some((t) => t.key === route.query.tab) ? (route.query.tab as TabKey) : "audit")
watch(tab, (value) => router.replace({ query: { ...route.query, tab: value } }))

// A refresh rebuilds the open tab, so it loads again
const refreshKey = ref(0)
function refresh() {
	refreshKey.value++
	overview.load()
}

// The employee whose quick view is open; every tab opens it from an employee's name
const quickView = ref<string | null>(null)
provide(OPEN_EMPLOYEE, (employee) => (quickView.value = employee))

const settingsOpen = ref(false)
const cycleKey = ref(0)
/** A new cycle start day changes every cycle, so the picker starts again at the company's current one. */
function onSettingsSaved() {
	state.from = state.to = ""
	cycleKey.value++
}

const tabProps = computed(() => ({
	scope: state,
	...(tab.value === "employees" ? { overview } : {}),
	// Processing changes slips, so the employees' payroll status reloads after it
	...(tab.value === "processing" ? { employees: rows.value, onChanged: overview.load } : {}),
}))
const badges = computed<Partial<Record<TabKey, number>>>(() => ({
	employees: rows.value.filter((r) => r.status === "Active").length,
	processing: rows.value.filter((r) => r.salary_slip).length,
}))
</script>
