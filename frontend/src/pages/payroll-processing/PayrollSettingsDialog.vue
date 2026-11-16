<template>
	<Dialog v-model:open="open" :title="`Payroll settings · ${company}`">
		<div v-if="settings" class="flex flex-col gap-4 text-[13px]">
			<div class="flex flex-col gap-1.5">
				<FormControl v-model="startDay" type="number" label="Pay cycle starts on day" :min="1" :max="28" :disabled="!settings.can_edit" />
				<p class="text-ch-ink-3">{{ cycleExample }}</p>
			</div>
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
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Checkbox, Dialog, FormControl, LoadingIndicator, toast } from "frappe-ui"
import { clearPayrollCycles } from "@/data/payroll"
import { getPayrollSettings, savePayrollSettings, type PayrollSettings } from "@/data/payrollDashboard"

/** The company's own pay cycle and advance recovery. Each company has its own settings. */
const props = defineProps<{ company: string }>()
const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>("open", { default: false })

const settings = ref<PayrollSettings | null>(null)
const startDay = ref<number | string>(1)
const autoRecover = ref(false)
const saving = ref(false)

watch(open, async (value) => {
	if (!value) return
	settings.value = null
	settings.value = await getPayrollSettings(props.company)
	startDay.value = settings.value.start_day
	autoRecover.value = !!settings.value.auto_recover_advances
})

const day = computed(() => Number(startDay.value))
const valid = computed(() => Number.isInteger(day.value) && day.value >= 1 && day.value <= 28)
const cycleExample = computed(() => {
	if (!valid.value) return "Choose a day from 1 to 28."
	if (day.value === 1) return "Calendar months: the July cycle runs from 1 July to 31 July."
	return `The July cycle runs from ${day.value} June to ${day.value - 1} July. A cycle is named after the month it ends in.`
})

async function save() {
	saving.value = true
	try {
		await savePayrollSettings(props.company, day.value, autoRecover.value)
		clearPayrollCycles(props.company)
		toast.success("Payroll settings saved")
		open.value = false
		emit("saved")
	} finally {
		saving.value = false
	}
}
</script>
