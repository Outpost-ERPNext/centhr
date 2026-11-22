<template>
	<Dialog v-model:open="open" :title="`Payroll settings · ${company}`" size="2xl">
		<div v-if="settings" class="flex flex-col gap-5 text-[13px]">
			<section class="flex flex-col gap-3">
				<h3 class="font-medium text-ch-ink">Pay cycle of {{ company }}</h3>
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<FormControl :model-value="settings.frequency" label="Frequency" disabled description="CentHR runs monthly pay cycles." />
					<FormControl v-model="startDay" type="number" label="Pay cycle starts on day" :min="1" :max="28" :disabled="!settings.can_edit" />
				</div>
				<p class="text-ch-ink-3">{{ cycleExample }}</p>
				<p v-if="nextCycle" class="rounded-4 bg-ch-subtle px-3 py-2 text-ch-ink-2">
					Next cycle: <b class="text-ch-ink">{{ formatDateShort(nextCycle.from) }} → {{ formatDateShort(nextCycle.to) }}</b>
				</p>
				<label class="flex items-start gap-2">
					<Checkbox v-model="autoRecover" :disabled="!settings.can_edit" />
					<span>
						<span class="text-ch-ink">Recover overdue advances in payroll</span>
						<span class="block text-ch-ink-3">
							When payroll is generated, employee advances that are past their due date are deducted from that cycle's salary.
							{{ settings.recovery_component ? `Deducted as ${settings.recovery_component}.` : "Needs the IOU Recovery Salary Component in CentHr Settings." }}
						</span>
					</span>
				</label>
				<div>
					<Button icon-left="lucide-lock" label="Confidential batches and auto-attendance" @click="rulesOpen = true" />
				</div>
			</section>

			<section class="flex flex-col gap-3 border-t border-ch-line pt-4">
				<div class="flex flex-wrap items-center gap-2">
					<h3 class="font-medium text-ch-ink">How salaries are worked out</h3>
					<StatusBadge pill tone="amber" status="Applies to all companies" />
				</div>
				<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
					<FormControl
						v-model="site.payroll_based_on"
						type="select"
						label="Working days are counted from"
						:options="['Leave', 'Attendance']"
						:disabled="!settings.can_edit"
						description="Leave: every day is paid unless it is unpaid leave. Attendance: only days marked as worked are paid."
					/>
					<FormControl
						v-model="site.consider_unmarked_attendance_as"
						type="select"
						label="A day without attendance counts as"
						:options="['Present', 'Absent']"
						:disabled="!settings.can_edit || site.payroll_based_on !== 'Attendance'"
						description="Used when working days are counted from attendance."
					/>
				</div>
				<label v-for="flag in FLAGS" :key="flag.key" class="flex items-start gap-2">
					<Checkbox :model-value="!!site[flag.key]" :disabled="!settings.can_edit" @update:model-value="(value) => (site[flag.key] = value ? 1 : 0)" />
					<span>
						<span class="text-ch-ink">{{ flag.label }}</span>
						<span class="block text-ch-ink-3">{{ flag.hint }}</span>
					</span>
				</label>
			</section>
			<p v-if="!settings.can_edit" class="text-ch-ink-3">Only an HR Manager can change these settings.</p>
		</div>
		<div v-else class="flex justify-center py-8"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="open = false" />
				<Button v-if="settings?.can_edit" variant="solid" label="Save" :disabled="!valid" :loading="saving" @click="save" />
			</div>
		</template>
	</Dialog>

	<StructureRulesDialog v-model:open="rulesOpen" :company="company" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Checkbox, Dialog, FormControl, LoadingIndicator, toast } from "frappe-ui"
import StatusBadge from "@/components/StatusBadge.vue"
import { clearPayrollCycles } from "@/data/payroll"
import { getPayrollSettings, savePayrollSettings, type PayrollSettings, type SiteSettings } from "@/data/payrollDashboard"
import { addDays, formatDateShort, toISODate, today } from "@/utils/format"
import StructureRulesDialog from "./StructureRulesDialog.vue"

const FLAGS: { key: "include_holidays_in_total_working_days" | "process_payroll_accounting_entry_based_on_employee"; label: string; hint: string }[] = [
	{
		key: "include_holidays_in_total_working_days",
		label: "Count holidays as working days",
		hint: "Holidays are part of the days a salary is spread over. Without it, a day of unpaid leave costs more.",
	},
	{
		key: "process_payroll_accounting_entry_based_on_employee",
		label: "Book payroll per employee",
		hint: "The accrual journal names each employee on the payroll payable line. Without it, one line carries the whole run.",
	},
]

/** The company's own pay cycle and advance recovery, and the calculation rules of HRMS's Payroll
 * Settings, which every company of the site shares. */
const props = defineProps<{ company: string }>()
const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>("open", { default: false })

const settings = ref<PayrollSettings | null>(null)
const startDay = ref<number | string>(1)
const autoRecover = ref(false)
const site = ref({} as SiteSettings)
const saving = ref(false)
const rulesOpen = ref(false)

watch(open, async (value) => {
	if (!value) return
	settings.value = null
	settings.value = await getPayrollSettings(props.company)
	startDay.value = settings.value.start_day
	autoRecover.value = !!settings.value.auto_recover_advances
	site.value = { ...settings.value.site }
})

const day = computed(() => Number(startDay.value))
const valid = computed(() => Number.isInteger(day.value) && day.value >= 1 && day.value <= 28)
const cycleExample = computed(() => {
	if (!valid.value) return "Choose a day from 1 to 28."
	if (day.value === 1) return "Calendar months: the July cycle runs from 1 July to 31 July."
	return `The July cycle runs from ${day.value} June to ${day.value - 1} July. A cycle is named after the month it ends in.`
})
/** The cycle after the one today falls in, for the start day in the form. */
const nextCycle = computed(() => {
	if (!valid.value) return null
	const now = new Date(`${today()}T00:00:00`)
	// The current cycle started this month, or last month when its start day is still to come
	const offset = now.getDate() >= day.value ? 1 : 0
	const from = new Date(now.getFullYear(), now.getMonth() + offset, day.value)
	const following = new Date(from.getFullYear(), from.getMonth() + 1, day.value)
	return { from: toISODate(from), to: addDays(toISODate(following), -1) }
})

async function save() {
	saving.value = true
	try {
		await savePayrollSettings(props.company, day.value, autoRecover.value, site.value)
		clearPayrollCycles(props.company)
		toast.success("Payroll settings saved")
		open.value = false
		emit("saved")
	} finally {
		saving.value = false
	}
}
</script>
