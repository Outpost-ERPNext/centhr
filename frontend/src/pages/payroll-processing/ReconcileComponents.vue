<template>
	<div class="overflow-x-auto rounded-4 border border-ch-line bg-ch-surface">
		<table class="w-full min-w-[640px] text-left">
			<thead class="text-ch-ink-3">
				<tr>
					<th class="px-3 py-2 font-normal">Salary component</th>
					<th class="px-3 py-2 font-normal">Type</th>
					<th class="px-3 py-2 text-right font-normal">ERP amount</th>
					<th class="px-3 py-2 font-normal">Sheet column</th>
					<th class="px-3 py-2 text-right font-normal">Excel amount</th>
					<th class="px-3 py-2 text-right font-normal">Variance</th>
					<th class="px-3 py-2 font-normal">Result</th>
				</tr>
			</thead>
			<tbody>
				<tr v-for="line in row.components" :key="line.component" class="border-t border-ch-line">
					<td class="px-3 py-1.5 font-medium text-ch-ink">{{ line.component }}</td>
					<td class="px-3 py-1.5"><StatusBadge :tone="line.type === 'Earning' ? 'green' : 'amber'" :status="line.type" /></td>
					<td class="px-3 py-1.5 text-right tabular-nums">{{ money(line.erp) }}</td>
					<td class="px-3 py-1.5 text-ch-ink-2">{{ line.column || "—" }}</td>
					<td class="px-3 py-1.5 text-right tabular-nums">{{ money(line.excel) }}</td>
					<td class="px-3 py-1.5 text-right tabular-nums" :class="line.differs ? 'font-medium text-ch-red-ink' : 'text-ch-ink-3'">{{ money(line.variance) }}</td>
					<td class="px-3 py-1.5"><StatusBadge pill :tone="result(line).tone" :status="result(line).label" /></td>
				</tr>
			</tbody>
			<tfoot>
				<tr class="border-t border-ch-line font-medium text-ch-ink">
					<td colspan="2" class="px-3 py-2 text-right text-ch-ink-3">Net pay</td>
					<td class="px-3 py-2 text-right tabular-nums">{{ money(row.erp_net_pay) }}</td>
					<td />
					<td class="px-3 py-2 text-right tabular-nums">{{ money(row.excel_net_pay) }}</td>
					<td class="px-3 py-2 text-right tabular-nums" :class="row.variance ? 'text-ch-red-ink' : 'text-ch-ink-3'">{{ money(row.variance) }}</td>
					<td />
				</tr>
			</tfoot>
		</table>
	</div>
</template>

<script setup lang="ts">
import StatusBadge from "@/components/StatusBadge.vue"
import type { ComponentLine, ReconcileRow } from "@/data/masterSheet"
import { formatCurrency } from "@/utils/format"
import type { Tone } from "@/utils/status"

/** An employee's salary components beside their columns of the master sheet. A component without a
 * column is unmapped: Map columns says which column it is. */
const props = defineProps<{ row: ReconcileRow }>()

const money = (value: number | null) => (value === null || value === undefined ? "—" : formatCurrency(value, props.row.currency))

function result(line: ComponentLine): { label: string; tone: Tone } {
	if (!line.column) return { label: "Unmapped", tone: "gray" }
	return line.differs ? { label: "Differs", tone: "red" } : { label: "Match", tone: "green" }
}
</script>
