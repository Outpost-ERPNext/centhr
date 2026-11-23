<template>
	<DocPageShell
		doctype="PMS Employee Relationship"
		list-label="PMS Employee Relationship"
		:page="page"
		:title="page.doc.value.employee_name || page.doc.value.name"
		:subtitle="page.isNew ? '' : [page.doc.value.department, page.doc.value.grade].filter(Boolean).join(' · ')"
		:link-filters="linkFilters"
		@change="onChange"
	>
		<template #actions>
			<DocActions :page="page">
				<Button
					v-if="!page.isNew && page.canEdit.value"
					:icon-left="locked ? 'lucide-lock-open' : 'lucide-lock'"
					:label="locked ? 'Unlock' : 'Lock'"
					:loading="busy"
					@click="toggleLock"
				/>
			</DocActions>
		</template>
		<template #status>
			<StatusBadge v-if="locked" pill tone="amber" status="Locked" />
			<span v-else />
		</template>
		<template v-if="locked" #notice>
			<p class="rounded-4 bg-ch-amber-bg px-3 py-2 text-[13px] text-ch-amber-ink">
				This mapping is locked. The peer mapping run leaves it alone, and it cannot be edited until it is unlocked.
			</p>
		</template>
		<template v-if="page.isNew" #before-form>
			<p class="text-[13px] text-ch-ink-3">
				Choose the company, then the employee and up to 2 peers of the same company. The department, grade and line manager come from
				the Employee record.
				Each peer also gets this employee as their peer when they have a free place.
			</p>
		</template>
	</DocPageShell>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, toast } from "frappe-ui"
import DocActions from "@/components/DocActions.vue"
import DocPageShell from "@/components/DocPageShell.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { useEmployeeDetails } from "@/data/employeeDetails"
import { setPeerMappingLock } from "@/data/pms"
import { useDocPage } from "@/data/useDocPage"

const props = defineProps<{ name: string | null }>()
const page = useDocPage("PMS Employee Relationship", props.name)

const locked = computed(() => !!page.doc.value.locked)
const busy = ref(false)
const details = useEmployeeDetails(page.doc, {
	employee_name: "employee_name",
	department: "department",
	designation: "designation",
	grade: "grade",
	line_manager: "reports_to",
	line_manager_name: "reports_to.employee_name",
	line_manager_designation: "reports_to.designation",
})
const onChange = details.onChange
const linkFilters = {
	...details.linkFilters,
	// A peer is another active employee of the same company
	"peers.employee": (doc: Record<string, any>) => [
		["status", "=", "Active"],
		...(doc.company ? [["company", "=", doc.company]] : []),
		...(doc.employee ? [["name", "!=", doc.employee]] : []),
	],
}

async function toggleLock() {
	busy.value = true
	try {
		const now = await setPeerMappingLock(page.doc.value.name, !locked.value)
		toast.success(now ? "Mapping locked" : "Mapping unlocked")
		await page.reload()
	} finally {
		busy.value = false
	}
}
</script>
