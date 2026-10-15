<template>
	<div class="flex flex-col gap-4">
		<div v-if="tabs.length > 1" class="-mx-1 flex gap-1 overflow-x-auto border-b border-ch-line px-1" role="tablist">
			<button
				v-for="tab in tabs"
				:key="tab.name"
				role="tab"
				:aria-selected="activeTab === tab.name"
				class="-mb-px h-10 shrink-0 border-b-2 px-2 text-[13.5px]"
				:class="
					activeTab === tab.name
						? 'border-ch-ink font-medium text-ch-ink'
						: 'border-transparent text-ch-ink-3 hover:text-ch-ink'
				"
				@click="activeTab = tab.name"
			>
				{{ tab.label }}
			</button>
		</div>

		<section v-if="promptName" class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5">
			<div class="grid grid-cols-1 gap-x-5 gap-y-4 md:grid-cols-2">
				<FieldControl
					:field="nameField"
					:model-value="doc.__newname"
					:doc="doc"
					:doctype="doctype"
					required
					:read-only="readOnly"
					:error="errors?.__newname"
					@update:model-value="(v) => setValue('__newname', v)"
				/>
			</div>
		</section>

		<template v-for="tab in tabs" :key="tab.name">
			<div v-show="tabs.length <= 1 || activeTab === tab.name" class="flex flex-col gap-4">
				<template v-for="(section, si) in tab.sections" :key="si">
					<section
						v-if="sectionVisible(section)"
						class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5"
					>
						<h3 v-if="section.label" class="mb-4 text-[14px] font-medium text-ch-ink">{{ section.label }}</h3>
						<div class="grid gap-x-5 gap-y-4" :class="gridClass(section.columns.length)">
							<div
								v-for="(column, ci) in section.columns"
								:key="ci"
								class="min-w-0"
								:class="
									section.columns.length === 1
										? 'grid grid-cols-1 gap-x-5 gap-y-4 md:grid-cols-2'
										: 'flex flex-col gap-4'
								"
							>
								<template v-for="field in column" :key="field.fieldname">
									<template v-if="fieldVisible(field)">
										<ChildTable
											v-if="field.fieldtype === 'Table' || field.fieldtype === 'Table MultiSelect'"
											class="md:col-span-2"
											v-model="doc[field.fieldname]"
											:field="field"
											:read-only="fieldReadOnly(field)"
											:required="required(field)"
										/>
										<FieldControl
											v-else
											:field="field"
											:model-value="doc[field.fieldname]"
											:doc="doc"
											:doctype="doctype"
											:required="required(field)"
											:read-only="fieldReadOnly(field)"
											:error="errors?.[field.fieldname]"
											:link-filters="linkFilters?.[field.fieldname]?.(doc)"
											:link-query="linkQueries?.[field.fieldname]"
											@update:model-value="(v) => setValue(field.fieldname, v)"
										/>
									</template>
								</template>
							</div>
						</div>
					</section>
				</template>
			</div>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { needsPromptName } from "@/data/doc"
import { getLayout, NO_VALUE_TYPES, type DocField, type LayoutSection } from "@/data/meta"
import { evaluateDependsOn, isReadOnly, isRequired } from "@/utils/dependsOn"
import ChildTable from "./fields/ChildTable.vue"
import FieldControl from "./fields/FieldControl.vue"

const props = defineProps<{
	doctype: string
	doc: Record<string, any>
	/** Fields to leave out of this form, on top of hidden ones. */
	hiddenFields?: string[]
	/** Fields the user may write (permlevel). Empty means no restriction known. */
	writableFields?: string[]
	readOnly?: boolean
	errors?: Record<string, string>
	linkFilters?: Record<string, (doc: Record<string, any>) => Record<string, any> | any[] | undefined>
	linkQueries?: Record<string, string>
	/** Fields required on top of the meta, e.g. by the company's entity sync. */
	requiredFields?: string[]
	/** Fields shown read-only on top of the meta, e.g. until a field they depend on is set. */
	readOnlyFields?: string[]
	/** Label of the name input for DocTypes the user names ("prompt"). */
	nameLabel?: string
}>()
const emit = defineEmits<{ change: [fieldname: string, value: any] }>()

// A prompt-named DocType has no name field; the server takes the name from __newname
const promptName = computed(() => needsPromptName(props.doctype, props.doc))
const nameField = computed<DocField>(() => ({ fieldname: "__newname", fieldtype: "Data", label: props.nameLabel || "Name", reqd: 1 }))

const tabs = computed(() => {
	const layout = getLayout(props.doctype)
	// Drop tabs with nothing to edit (Connections, dashboards)
	return layout.filter((tab) =>
		tab.sections.some((s) => s.columns.some((c) => c.some((f) => !f.hidden && !NO_VALUE_TYPES.includes(f.fieldtype))))
	)
})
const activeTab = ref("")
watch(
	tabs,
	(value) => {
		if (!value.some((t) => t.name === activeTab.value)) activeTab.value = value[0]?.name || ""
	},
	{ immediate: true }
)

function fieldVisible(field: DocField) {
	if (NO_VALUE_TYPES.includes(field.fieldtype)) return false
	if (field.hidden || props.hiddenFields?.includes(field.fieldname)) return false
	return evaluateDependsOn(field.depends_on, props.doc)
}

function required(field: DocField) {
	return isRequired(field, props.doc) || !!props.requiredFields?.includes(field.fieldname)
}

function fieldReadOnly(field: DocField) {
	if (props.readOnly || props.readOnlyFields?.includes(field.fieldname)) return true
	if (isReadOnly(field, props.doc)) return true
	if (props.writableFields?.length && !props.writableFields.includes(field.fieldname)) return true
	return false
}

function sectionVisible(section: LayoutSection) {
	if (!evaluateDependsOn(section.dependsOn, props.doc)) return false
	return section.columns.some((c) => c.some(fieldVisible))
}

function gridClass(columns: number) {
	if (columns >= 3) return "grid-cols-1 md:grid-cols-3"
	if (columns === 2) return "grid-cols-1 md:grid-cols-2"
	return "grid-cols-1"
}

function setValue(fieldname: string, value: any) {
	if (props.doc[fieldname] === value) return
	// eslint-disable-next-line vue/no-mutating-props
	props.doc[fieldname] = value
	emit("change", fieldname, value)
}
</script>
