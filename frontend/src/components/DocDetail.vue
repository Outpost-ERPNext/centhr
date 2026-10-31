<template>
	<div class="flex flex-col gap-5">
		<template v-for="(section, si) in sections" :key="si">
			<div v-if="section.fields.length">
				<h3 v-if="section.label" class="mb-3 text-[13px] font-medium text-ch-ink-2">{{ section.label }}</h3>
				<div class="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-2">
					<div
						v-for="field in section.fields"
						:key="field.fieldname"
						class="flex min-w-0 flex-col gap-0.5 rounded-3 bg-ch-subtle px-3 py-2"
						:class="field.fieldtype === 'Table' || TEXT_TYPES.includes(field.fieldtype) ? 'col-span-full' : ''"
					>
						<span class="text-[12px] text-ch-ink-3">{{ field.label }}</span>
						<template v-if="field.fieldtype === 'Table'">
							<div v-if="doc[field.fieldname]?.length" class="overflow-x-auto">
								<table class="mt-1 w-full min-w-[480px] text-[13px]">
									<thead class="text-left text-ch-ink-3">
										<tr>
											<th v-for="col in childColumns(field)" :key="col.fieldname" class="py-1 pr-3 font-normal">
												{{ col.label }}
											</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="row in doc[field.fieldname]" :key="row.name" class="border-t border-ch-line">
											<td v-for="col in childColumns(field)" :key="col.fieldname" class="py-1 pr-3">
												{{ cellText(row, col) }}
											</td>
										</tr>
									</tbody>
								</table>
							</div>
							<span v-else class="text-[13.5px] text-ch-ink-4">—</span>
						</template>
						<RouterLink
							v-else-if="field.fieldtype === 'Link' && routeFor(field.options, doc[field.fieldname])"
							:to="routeFor(field.options, doc[field.fieldname])!"
							class="truncate text-[13.5px] text-ch-ink underline decoration-ch-line-2 underline-offset-2 hover:decoration-ch-ink"
						>
							{{ doc[field.fieldname] }}
						</RouterLink>
						<span
							v-else
							class="text-[13.5px] text-ch-ink"
							:class="TEXT_TYPES.includes(field.fieldtype) ? 'whitespace-pre-wrap' : 'truncate'"
							:title="String(display(field))"
						>
							{{ display(field) || "—" }}
						</span>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import { getMeta, NO_VALUE_TYPES, type DocField, type LayoutTab } from "@/data/meta"
import { stripHtml } from "@/data/api"
import { evaluateDependsOn } from "@/utils/dependsOn"
import { displayValue } from "@/utils/format"
import { routeFor } from "@/utils/routes"

const TEXT_TYPES = ["Small Text", "Text", "Long Text", "Text Editor"]

const props = defineProps<{
	doctype: string
	doc: Record<string, any>
	tab: LayoutTab
	hiddenFields?: string[]
	/** Show empty fields too. Off by default to keep long forms short. */
	showEmpty?: boolean
}>()

const sections = computed(() =>
	props.tab.sections
		.filter((s) => evaluateDependsOn(s.dependsOn, props.doc))
		.map((s) => ({
			label: s.label,
			fields: s.columns.flat().filter((f) => {
				if (NO_VALUE_TYPES.includes(f.fieldtype) || f.hidden || f.fieldname === "naming_series") return false
				if (props.hiddenFields?.includes(f.fieldname)) return false
				if (!evaluateDependsOn(f.depends_on, props.doc)) return false
				const value = props.doc[f.fieldname]
				if (props.showEmpty) return true
				if (f.fieldtype === "Check") return true
				return !(value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length))
			}),
		}))
)

function display(field: DocField) {
	const currency = field.fieldtype === "Currency" && field.options ? props.doc[field.options] : null
	return displayValue(props.doc[field.fieldname], field.fieldtype, currency)
}

// Text Editor cells hold HTML; the table shows their text
function cellText(row: Record<string, any>, col: DocField) {
	const value = row[col.fieldname]
	return typeof value === "string" && /<[a-z]/i.test(value) ? stripHtml(value) : displayValue(value, col.fieldtype)
}

function childColumns(field: DocField) {
	const fields = (getMeta(field.options || "")?.fields || []).filter(
		(f) => !NO_VALUE_TYPES.includes(f.fieldtype) && !f.hidden
	)
	const listed = fields.filter((f) => f.in_list_view)
	return (listed.length ? listed : fields).slice(0, 6)
}
</script>
