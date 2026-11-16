<template>
	<PageHeader :crumbs="[{ label: 'My Reviews' }]">
		<template #actions>
			<Button icon-left="lucide-rotate-ccw" label="Refresh" @click="load" />
		</template>
	</PageHeader>

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<p class="px-5 pt-3 text-[13px] text-ch-ink-3">
			The colleagues you are asked to review. Your ratings are used for their 360 score; they do not see who gave which rating.
		</p>
		<div class="px-5 py-3">
			<SegmentedTabs v-model="tab" :tabs="tabs" />
		</div>

		<DataTable
			:columns="columns"
			:rows="shown"
			:loading="loading"
			:error="error"
			empty-icon="lucide-clipboard-check"
			:empty-message="tab === 'Pending' ? 'You have no reviews to give' : 'You have not given a review yet'"
			mobile-aside="status"
			@row-click="(row) => router.push(`/pms/reviews/${encodeURIComponent(row.name)}`)"
		>
			<template #cell-reviewee_name="{ row }">
				<div class="min-w-0">
					<div class="truncate font-medium text-ch-ink">{{ row.reviewee_name }}</div>
					<div class="truncate text-[12px] text-ch-ink-3">{{ row.department }}</div>
				</div>
			</template>
			<template #cell-status="{ row }">
				<StatusBadge :tone="row.status === 'Completed' ? 'green' : 'amber'" :status="row.status === 'Completed' ? 'Submitted' : 'To do'" />
			</template>
		</DataTable>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import DataTable, { type Column } from "@/components/DataTable.vue"
import SegmentedTabs from "@/components/SegmentedTabs.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getMyReviews, type ReviewRow } from "@/data/pmsReview"
import { formatDateShort } from "@/utils/format"

const router = useRouter()
const rows = ref<ReviewRow[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const tab = ref("Pending")

async function load() {
	loading.value = true
	error.value = null
	try {
		rows.value = await getMyReviews()
	} catch (e: any) {
		error.value = e?.messages?.[0] || "Could not load your reviews"
	} finally {
		loading.value = false
	}
}
load()

const count = (status: string) => rows.value.filter((row) => row.status === status).length
const tabs = computed(() => [
	{ label: "To do", value: "Pending", count: count("Pending") },
	{ label: "Submitted", value: "Completed", count: count("Completed") },
])
const shown = computed(() => rows.value.filter((row) => row.status === tab.value))

const columns: Column[] = [
	{ key: "reviewee_name", label: "Colleague", width: "minmax(220px,2fr)" },
	{ key: "relationship_type", label: "You review as", width: "150px", format: (v) => (v === "Peers" ? "Peer" : v) },
	{ key: "quarter", label: "Quarter", width: "130px", format: (_, row) => `${row.quarter} ${row.fiscal_year}` },
	{ key: "status", label: "Status", width: "120px" },
	{ key: "review_date", label: "Submitted on", width: "130px", hideOnMobile: true, format: (v) => (v ? formatDateShort(v) : "—") },
]
</script>
