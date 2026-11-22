<template>
	<Dialog v-model:open="open" title="Hold salary">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-2">
				Hold {{ employee?.employee_name }}'s salary from {{ cycleLabel(scope.from, scope.to) }} on? Each salary slip of the hold is marked
				Withheld and left out of the payment until you release it.
			</p>
			<FormControl v-model="length" type="select" label="Hold for" :options="LENGTHS" />
			<FormControl v-if="length === 'several'" v-model="cycles" type="number" label="Number of pay cycles" :min="2" :max="24" />
			<FormControl
				v-model="reason"
				type="textarea"
				label="Reason for the hold"
				:rows="3"
				placeholder="For example: disciplinary case open, bank details to confirm"
			/>
			<p class="text-ch-ink-3">The reason is kept on the hold and shown in this list.</p>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="open = false" />
				<Button variant="solid" theme="red" label="Set hold" :disabled="!reason.trim()" :loading="saving" @click="save" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { Button, Dialog, FormControl, toast } from "frappe-ui"
import { cycleLabel } from "@/data/payroll"
import { setHold, type AuditRow, type Scope } from "@/data/payrollDashboard"

const LENGTHS = [
	{ label: "This pay cycle only", value: "one" },
	{ label: "Several pay cycles", value: "several" },
	{ label: "Until it is released", value: "open" },
]

/** Why and for how long an employee's salary is held back. */
const props = defineProps<{ scope: Scope; employee: AuditRow | null }>()
const emit = defineEmits<{ saved: [] }>()
const open = defineModel<boolean>("open", { default: false })

const length = ref("one")
const cycles = ref(2)
const reason = ref("")
const saving = ref(false)
watch(open, (value) => {
	if (!value) return
	length.value = "one"
	cycles.value = 2
	reason.value = ""
})

async function save() {
	saving.value = true
	try {
		// 0 cycles holds the salary until someone releases it
		const count = length.value === "one" ? 1 : length.value === "open" ? 0 : Math.max(2, Number(cycles.value) || 2)
		await setHold(props.employee!.name, props.scope, reason.value.trim(), count)
		toast.success("Salary on hold")
		open.value = false
		emit("saved")
	} finally {
		saving.value = false
	}
}
</script>
