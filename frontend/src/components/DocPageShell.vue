<template>
	<PageHeader :crumbs="crumbs">
		<template #actions>
			<slot name="actions">
				<DocActions :page="page" />
			</slot>
		</template>
	</PageHeader>

	<div class="flex-1 overflow-y-auto bg-ch-sb">
		<div v-if="page.loading.value" class="flex justify-center py-20">
			<LoadingIndicator class="size-5 text-ch-ink-3" />
		</div>
		<div v-else-if="page.notFound.value" class="mx-auto flex max-w-md flex-col items-center gap-3 px-5 py-20 text-center">
			<span class="lucide-file-x size-6 text-ch-ink-4" />
			<p class="text-sm text-ch-ink-2">{{ page.notFound.value }}</p>
			<Button :route="listRoute" label="Back to list" />
		</div>
		<div v-else class="mx-auto flex max-w-[1240px] flex-col gap-4 p-4 sm:p-5">
			<div class="flex flex-wrap items-center gap-3">
				<slot name="avatar" />
				<div class="min-w-0 flex-1">
					<h1 class="truncate text-[20px] font-semibold tracking-[-0.01em] text-ch-ink">
						{{ page.isNew ? `New ${doctypeLabel}` : title }}
					</h1>
					<p v-if="subtitle" class="truncate text-[13px] text-ch-ink-3">{{ subtitle }}</p>
				</div>
				<slot name="status">
					<StatusBadge
						v-if="!page.isNew && page.isSubmittable.value"
						pill
						:status="docstatusLabel(page.docstatus.value)"
					/>
				</slot>
				<span v-if="!page.isNew" class="text-[13px] tabular-nums text-ch-ink-3">{{ page.doc.value.name }}</span>
			</div>

			<slot name="notice" />

			<div class="grid grid-cols-1 gap-4" :class="$slots.aside ? 'lg:grid-cols-[minmax(0,2fr)_minmax(280px,1fr)]' : ''">
				<div class="flex min-w-0 flex-col gap-4">
					<slot v-if="page.editing.value" name="before-form" />
					<DocForm
						v-if="page.editing.value"
						:doctype="doctype"
						:doc="page.doc.value"
						:writable-fields="page.writableFields.value"
						:hidden-fields="hiddenFields"
						:link-filters="linkFilters"
						:link-queries="linkQueries"
						:required-fields="requiredFields"
						:read-only-fields="readOnlyFields"
						:name-label="nameLabel"
						:field-options="fieldOptions"
						:buttons="buttons"
						@change="(f, v) => $emit('change', f, v)"
					/>
					<template v-else>
						<slot name="before-details" />
						<section class="rounded-5 border border-ch-line bg-ch-surface">
							<div
								v-if="viewTabs.length > 1"
								class="flex gap-1 overflow-x-auto border-b border-ch-line px-3"
								role="tablist"
							>
								<button
									v-for="tab in viewTabs"
									:key="tab.name"
									role="tab"
									:aria-selected="activeTab === tab.name"
									class="-mb-px h-11 shrink-0 border-b-2 px-2 text-[13.5px]"
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
							<div class="p-4 sm:p-5">
								<slot :name="`tab-${activeTab}`" :tab="currentTab">
									<DocDetail
										v-if="currentTab"
										:doctype="doctype"
										:doc="page.doc.value"
										:tab="currentTab"
										:hidden-fields="hiddenFields"
										:show-empty="showEmpty"
									/>
								</slot>
							</div>
						</section>
						<ActivityPanel
							v-if="!page.isNew"
							:doctype="doctype"
							:doc="page.doc.value"
							:docinfo="page.docinfo.value"
							:can-comment="page.permissions.value.read"
							@commented="page.reload"
						/>
					</template>
				</div>
				<aside v-if="$slots.aside" class="flex min-w-0 flex-col gap-4">
					<slot name="aside" />
				</aside>
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { Button, LoadingIndicator } from "frappe-ui"
import PageHeader from "./layout/PageHeader.vue"
import ActivityPanel from "./ActivityPanel.vue"
import DocActions from "./DocActions.vue"
import DocDetail from "./DocDetail.vue"
import DocForm, { type FormButton } from "./DocForm.vue"
import StatusBadge from "./StatusBadge.vue"
import { getLayout, NO_VALUE_TYPES, type LayoutTab } from "@/data/meta"
import type { useDocPage } from "@/data/useDocPage"
import { docstatusLabel } from "@/utils/status"
import { listRouteFor } from "@/utils/routes"

const props = defineProps<{
	doctype: string
	page: ReturnType<typeof useDocPage>
	listLabel: string
	title?: string
	subtitle?: string
	hiddenFields?: string[]
	linkFilters?: Record<string, (doc: Record<string, any>) => Record<string, any> | any[] | undefined>
	linkQueries?: Record<string, string>
	requiredFields?: string[]
	readOnlyFields?: string[]
	/** Label of the name input for DocTypes the user names ("prompt"). */
	nameLabel?: string
	/** Choices of Autocomplete fields in the form. */
	fieldOptions?: Record<string, { label: string; value: string }[]>
	/** Handlers for the DocType's Button fields in the form. */
	buttons?: Record<string, FormButton>
	/** Show every field in the read view, including empty ones. */
	showEmpty?: boolean
	/** Extra read-only tabs, inserted after the given tab name (or appended). */
	extraTabs?: { name: string; label: string; after?: string }[]
}>()
defineEmits<{ change: [fieldname: string, value: any] }>()

const doctypeLabel = computed(() => props.doctype)
const listRoute = computed(() => listRouteFor(props.doctype) || "/")

const crumbs = computed(() => [
	{ label: props.listLabel, route: listRoute.value },
	{ label: props.page.isNew ? "New" : props.title || props.page.doc.value.name || "" },
])

const viewTabs = computed(() => {
	const tabs: { name: string; label: string; layout?: LayoutTab }[] = getLayout(props.doctype)
		.filter((tab) =>
			tab.sections.some((s) =>
				s.columns.some((c) => c.some((f) => !f.hidden && !NO_VALUE_TYPES.includes(f.fieldtype)))
			)
		)
		.map((tab) => ({ name: tab.name, label: tab.label, layout: tab }))
	for (const extra of props.extraTabs || []) {
		const index = extra.after ? tabs.findIndex((t) => t.name === extra.after) : -1
		const entry = { name: extra.name, label: extra.label }
		if (index >= 0) tabs.splice(index + 1, 0, entry)
		else tabs.push(entry)
	}
	return tabs
})

const activeTab = ref("")
watch(
	viewTabs,
	(tabs) => {
		if (!tabs.some((t) => t.name === activeTab.value)) activeTab.value = tabs[0]?.name || ""
	},
	{ immediate: true }
)
const currentTab = computed(() => viewTabs.value.find((t) => t.name === activeTab.value)?.layout)
</script>
