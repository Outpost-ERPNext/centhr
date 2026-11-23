<template>
	<Dialog v-model:open="open" title="KPI Templates for a department" size="3xl">
		<div class="flex flex-col gap-4 text-[13px]">
			<p class="text-ch-ink-3">
				Every active employee of the department gets a draft KPI Template with these KPIs. Employees who already have a template for the
				month keep it. Choose a designation to give the KPIs only to that role.
			</p>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<LinkField v-model="form.fiscal_year" doctype="Fiscal Year" label="Fiscal year" required size="md" />
				<FormControl v-model="form.month" type="select" label="Month" :options="MONTH_OPTIONS" required />
				<LinkField v-model="form.company" doctype="Company" label="Company" size="md" />
				<LinkField v-model="form.department" doctype="Department" label="Department" :filters="departmentFilters" required size="md" />
				<LinkField v-model="form.designation" doctype="Designation" label="Designation" :filters="{ disabled: 0 }" size="md" />
			</div>
			<ChildTable v-if="metaReady" v-model="form.items" :field="ITEMS_FIELD" required />
			<p class="tabular-nums" :class="totalWeight > 100 ? 'text-ch-red-ink' : 'text-ch-ink-3'">
				Total weight {{ totalWeight }} of 100
			</p>
		</div>
		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="open = false" />
				<Button variant="solid" label="Create templates" :disabled="!canCreate" :loading="busy" @click="create" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue"
import { Button, Dialog, FormControl, toast } from "frappe-ui"
import ChildTable from "@/components/fields/ChildTable.vue"
import LinkField from "@/components/fields/LinkField.vue"
import { loadMeta, type DocField } from "@/data/meta"
import { createKpiTemplates, currentMonth, getCurrentFiscalYear, MONTHS } from "@/data/pms"

const open = defineModel<boolean>("open", { default: false })
const emit = defineEmits<{ created: [] }>()

const MONTH_OPTIONS = MONTHS.map((month) => ({ label: month, value: month }))
// The same rows as the KPIs table of a KPI Template
const ITEMS_FIELD: DocField = { fieldname: "items", fieldtype: "Table", label: "KPIs", options: "KPI Template Item" }

const form = reactive({
	fiscal_year: null as string | null,
	month: currentMonth(),
	// Only narrows the department list; a department belongs to one company
	company: null as string | null,
	department: null as string | null,
	designation: null as string | null,
	items: [] as Record<string, any>[],
})
const metaReady = ref(false)
const busy = ref(false)

watch(open, async (value) => {
	if (!value) return
	await loadMeta("KPI Template")
	metaReady.value = true
	form.fiscal_year ||= await getCurrentFiscalYear()
})

const departmentFilters = computed(() => ({ is_group: 0, ...(form.company ? { company: form.company } : {}) }))
watch(
	() => form.company,
	() => (form.department = null)
)

const totalWeight = computed(() => form.items.reduce((sum, row) => sum + (Number(row.weight) || 0), 0))
const complete = (row: Record<string, any>) => row.kpi && row.uom && row.weight && row.target !== undefined && row.target !== null && row.target !== ""
const canCreate = computed(
	() => !!form.fiscal_year && !!form.department && form.items.length > 0 && form.items.every(complete) && totalWeight.value <= 100
)

async function create() {
	busy.value = true
	try {
		const outcome = await createKpiTemplates({
			fiscal_year: form.fiscal_year!,
			month: form.month,
			department: form.department!,
			designation: form.designation,
			items: form.items,
		})
		const skipped = outcome.skipped ? `, ${outcome.skipped} already had one` : ""
		toast.success(`${outcome.created.length} draft templates created${skipped}`)
		open.value = false
		form.items = []
		emit("created")
	} finally {
		busy.value = false
	}
}
</script>
