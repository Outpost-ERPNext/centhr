<template>
	<Dialog v-model:open="open" title="Map columns" size="3xl">
		<div class="flex flex-col gap-3 text-[13px]">
			<p class="text-ch-ink-3">
				Say which column of the master sheet holds each thing CentHR compares. Columns with a familiar header are matched already. Your
				choices are saved for {{ scope.company }} and used for its later sheets too.
			</p>
			<div class="flex flex-wrap items-center gap-2">
				<div class="relative w-full sm:w-56">
					<span class="lucide-search pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-ch-ink-3" />
					<input
						v-model="search"
						type="search"
						placeholder="Search field or component"
						aria-label="Search field or component"
						class="h-7 w-full rounded-3 border-0 bg-ch-subtle pl-7 pr-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4 focus:ring-2 focus:ring-[var(--ch-line-2)]"
					/>
				</div>
				<SegmentedTabs v-model="filter" :tabs="tabs" />
				<Button class="ml-auto" icon-left="lucide-rotate-ccw" label="Reset to auto-match" :disabled="!data" @click="reset" />
			</div>

			<div v-if="data" class="max-h-[50vh] overflow-auto rounded-4 border border-ch-line">
				<table class="w-full min-w-[560px] text-left">
					<thead class="sticky top-0 z-[1] bg-ch-subtle text-ch-ink-3">
						<tr>
							<th class="px-3 py-2 font-normal">CentHR compares</th>
							<th class="px-3 py-2 font-normal">Type</th>
							<th class="px-3 py-2 font-normal">Column of the sheet</th>
							<th class="px-3 py-2 font-normal">Status</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="target in shown" :key="target.key" class="border-t border-ch-line">
							<td class="px-3 py-1.5 font-medium text-ch-ink">
								{{ target.label }}<span v-if="target.required" class="text-ch-red-ink" title="Needed to compare the sheet"> *</span>
							</td>
							<td class="px-3 py-1.5"><StatusBadge :tone="TYPE_TONES[target.type]" :status="target.type" /></td>
							<td class="px-3 py-1.5">
								<select
									v-model="chosen[target.key]"
									:aria-label="`Column of the sheet for ${target.label}`"
									class="h-7 w-full max-w-[280px] rounded-3 border-0 bg-ch-subtle px-2 text-[13px] text-ch-ink focus:ring-2 focus:ring-[var(--ch-line-2)]"
								>
									<option value="">Not mapped</option>
									<option v-for="header in data.headers" :key="header" :value="header">{{ header }}</option>
								</select>
							</td>
							<td class="px-3 py-1.5">
								<StatusBadge pill :tone="chosen[target.key] ? 'green' : target.required ? 'red' : 'gray'" :status="chosen[target.key] ? 'Mapped' : 'Unmapped'" />
							</td>
						</tr>
						<tr v-if="!shown.length">
							<td colspan="4" class="px-3 py-6 text-center text-ch-ink-3">Nothing matches the search</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-else class="flex justify-center py-10"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
			<p v-if="missing.length" class="rounded-4 bg-ch-amber-bg px-3 py-2 text-ch-amber-ink">
				{{ missing.join(" and ") }} must be mapped before the sheet can be compared.
			</p>
		</div>

		<template #actions>
			<div class="flex justify-end gap-2">
				<Button label="Cancel" @click="open = false" />
				<Button variant="solid" label="Save mapping" :disabled="!data" :loading="saving" @click="save" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, Dialog, LoadingIndicator, toast } from "frappe-ui"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getColumnMapping, saveColumnMapping, type ColumnMapping, type MappingTarget, type Reconciliation } from "@/data/masterSheet"
import type { Scope } from "@/data/payrollDashboard"
import type { Tone } from "@/utils/status"

const TYPE_TONES: Record<MappingTarget["type"], Tone> = { Field: "blue", Earning: "green", Deduction: "amber" }

/** Which column of the cycle's master sheet is what: the totals compared, and each salary component. */
const props = defineProps<{ scope: Scope }>()
const emit = defineEmits<{ saved: [result: Reconciliation] }>()
const open = defineModel<boolean>("open", { default: false })

const data = ref<ColumnMapping | null>(null)
// Header chosen per target; empty for not mapped
const chosen = ref<Record<string, string>>({})
const search = ref("")
const filter = ref("all")
const saving = ref(false)

watch(open, async (value) => {
	if (!value) return
	data.value = null
	search.value = ""
	filter.value = "all"
	data.value = await getColumnMapping(props.scope)
	chosen.value = withBlanks(data.value.mapping)
})

const withBlanks = (mapping: Record<string, string | null>) =>
	Object.fromEntries(Object.entries(mapping).map(([key, header]) => [key, header || ""]))

const targets = computed(() => data.value?.targets || [])
const mapped = computed(() => targets.value.filter((t) => chosen.value[t.key]).length)
const tabs = computed(() => [
	{ label: "All", value: "all", count: targets.value.length },
	{ label: "Mapped", value: "mapped", count: mapped.value },
	{ label: "Unmapped", value: "unmapped", count: targets.value.length - mapped.value },
])
const shown = computed(() => {
	const term = search.value.trim().toLowerCase()
	return targets.value
		.filter((t) => filter.value === "all" || (filter.value === "mapped") === !!chosen.value[t.key])
		.filter((t) => !term || t.label.toLowerCase().includes(term))
})
const missing = computed(() => targets.value.filter((t) => t.required && !chosen.value[t.key]).map((t) => t.label))

function reset() {
	chosen.value = withBlanks(data.value!.auto)
}

async function save() {
	saving.value = true
	try {
		emit("saved", await saveColumnMapping(props.scope, chosen.value))
		toast.success("Column mapping saved")
		open.value = false
	} finally {
		saving.value = false
	}
}
</script>
