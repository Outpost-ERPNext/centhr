<template>
	<CollapsibleSection title="Pre-audit checks" storage-key="payroll-audit" :summary="summary">
		<template #badge>
			<StatusBadge v-for="s in severities" :key="s.severity" pill :tone="SEVERITY_TONE[s.severity]" :status="`${s.count} ${s.severity}`" />
		</template>

		<p v-if="loading" class="px-1 text-[13px] text-ch-ink-3">Checking…</p>
		<p v-else-if="!results.length" class="flex items-center gap-2 px-1 text-[13px] text-ch-green-ink">
			<span class="lucide-circle-check size-4" /> All checks passed for these employees.
		</p>
		<div v-else class="flex flex-col divide-y divide-ch-line">
			<details v-for="result in results" :key="result.key" class="group py-1.5">
				<summary class="flex cursor-pointer list-none items-center gap-2.5 rounded-3 px-1 py-1 text-[13px] hover:bg-ch-hover">
					<span class="lucide-chevron-right size-3.5 text-ch-ink-3 transition-transform group-open:rotate-90" />
					<span class="size-2 shrink-0 rounded-full" :style="{ background: `var(--ch-${SEVERITY_TONE[result.severity]}-dot)` }" />
					<span class="font-medium text-ch-ink">{{ result.label }}</span>
					<span class="tabular-nums text-ch-ink-3">{{ result.rows.length }}</span>
					<span class="ml-auto hidden truncate text-[12.5px] text-ch-ink-3 md:block">{{ result.hint }}</span>
				</summary>
				<div class="flex flex-wrap gap-1.5 px-7 pb-1.5 pt-2">
					<RouterLink
						v-for="row in result.rows.slice(0, MAX_LISTED)"
						:key="row.name"
						:to="routeFor('Employee', row.name)!"
						class="rounded-full bg-ch-subtle px-2 py-0.5 text-[12px] text-ch-ink-2 hover:text-ch-ink"
					>
						{{ row.employee_name }} · {{ row.name }}
					</RouterLink>
					<span v-if="result.rows.length > MAX_LISTED" class="px-1 text-[12px] text-ch-ink-3">
						and {{ result.rows.length - MAX_LISTED }} more
					</span>
				</div>
			</details>
		</div>
	</CollapsibleSection>
</template>

<script setup lang="ts">
import { computed } from "vue"
import CollapsibleSection from "@/components/CollapsibleSection.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { SEVERITY_TONE, runAudit, type Severity } from "@/data/payrollAudit"
import type { Period, SalaryRow } from "@/data/salaryOverview"
import { routeFor } from "@/utils/routes"

const MAX_LISTED = 50

const props = defineProps<{ rows: SalaryRow[]; period: Period; loading?: boolean }>()

const results = computed(() => runAudit(props.rows, props.period))
const severities = computed(() =>
	(["error", "warning"] as Severity[])
		.map((severity) => ({ severity, count: results.value.filter((r) => r.severity === severity).length }))
		.filter((s) => s.count)
)
const summary = computed(() =>
	props.loading ? "" : results.value.length ? `${results.value.length} checks need a look` : "All clear"
)
</script>
