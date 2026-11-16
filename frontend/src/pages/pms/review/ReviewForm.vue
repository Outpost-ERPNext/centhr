<template>
	<PageHeader :crumbs="[{ label: 'My Reviews', route: '/pms/reviews' }, { label: form?.reviewee_name || 'Review' }]" />

	<div class="flex-1 overflow-y-auto bg-ch-sb">
		<div v-if="loading" class="flex justify-center py-20"><LoadingIndicator class="size-5 text-ch-ink-3" /></div>
		<div v-else-if="!form" class="mx-auto flex max-w-md flex-col items-center gap-3 px-5 py-20 text-center">
			<span class="lucide-file-x size-6 text-ch-ink-4" />
			<p class="text-sm text-ch-ink-2">{{ error || "This review is not asked of you." }}</p>
			<Button route="/pms/reviews" label="Back to my reviews" />
		</div>
		<div v-else class="mx-auto flex max-w-[860px] flex-col gap-4 p-4 sm:p-5">
			<section class="flex flex-wrap items-center gap-4 rounded-5 border border-ch-line bg-ch-surface p-4">
				<img v-if="form.company_logo" :src="form.company_logo" alt="" class="h-10 max-w-[140px] object-contain" />
				<div class="min-w-0 flex-1">
					<h1 class="truncate text-[20px] font-semibold tracking-[-0.01em] text-ch-ink">{{ form.reviewee_name }}</h1>
					<p class="truncate text-[13px] text-ch-ink-3">
						{{ [form.reviewee_designation, form.department].filter(Boolean).join(" · ") }}
					</p>
				</div>
				<div class="text-right text-[13px] text-ch-ink-3">
					<div>{{ form.quarter }} {{ form.fiscal_year }}</div>
					<div>You review as {{ form.relationship_type === "Peers" ? "a peer" : "line manager" }}</div>
				</div>
				<StatusBadge pill :tone="done ? 'green' : 'amber'" :status="done ? 'Submitted' : 'To do'" />
			</section>

			<p v-if="!done" class="text-[13px] text-ch-ink-3">Rate each statement from 1 (lowest) to 5 (highest). A remark is optional.</p>

			<section
				v-for="(question, index) in form.questions"
				:key="index"
				class="flex flex-col gap-3 rounded-5 border border-ch-line bg-ch-surface p-4"
			>
				<div class="flex items-start gap-2">
					<span class="w-5 shrink-0 text-right text-[13px] tabular-nums text-ch-ink-3">{{ index + 1 }}</span>
					<div class="min-w-0">
						<p class="text-[14px] text-ch-ink">{{ question.question }}</p>
						<p v-if="question.question_trait" class="text-[12px] text-ch-ink-3">{{ question.question_trait }}</p>
					</div>
				</div>
				<div class="flex flex-wrap items-center gap-1.5 pl-7" role="radiogroup" :aria-label="`Rating for question ${index + 1}`">
					<button
						v-for="value in RATINGS"
						:key="value"
						type="button"
						role="radio"
						:aria-checked="ratings[index] === value"
						:disabled="done"
						class="flex size-9 items-center justify-center rounded-4 border text-[14px] tabular-nums"
						:class="
							ratings[index] === value
								? 'border-ch-primary bg-ch-primary font-medium text-ch-on-primary'
								: 'border-ch-line text-ch-ink-2 enabled:hover:bg-ch-hover'
						"
						@click="ratings[index] = value"
					>
						{{ value }}
					</button>
				</div>
				<textarea
					v-if="!done || questionRemarks[index]"
					v-model="questionRemarks[index]"
					:readonly="done"
					rows="2"
					placeholder="Remark (optional)"
					:aria-label="`Remark for question ${index + 1}`"
					class="ml-7 rounded-3 border-0 bg-ch-subtle px-2 py-1.5 text-[13px] text-ch-ink placeholder:text-ch-ink-4"
				/>
			</section>

			<section class="flex flex-col gap-2 rounded-5 border border-ch-line bg-ch-surface p-4">
				<label for="review-remarks" class="text-[13px] text-ch-ink-2">Overall remarks</label>
				<textarea
					id="review-remarks"
					v-model="remarks"
					:readonly="done"
					rows="3"
					class="rounded-3 border-0 bg-ch-subtle px-2 py-1.5 text-[13px] text-ch-ink"
				/>
			</section>

			<div v-if="!done" class="flex items-center justify-end gap-3">
				<span class="text-[13px] text-ch-ink-3">{{ rated }} of {{ form.questions.length }} rated</span>
				<Button variant="solid" label="Submit review" :disabled="rated < form.questions.length" :loading="submitting" @click="confirmSubmit" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, LoadingIndicator, dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import StatusBadge from "@/components/StatusBadge.vue"
import { getReviewForm, submitReview, type ReviewForm } from "@/data/pmsReview"

const RATINGS = [1, 2, 3, 4, 5]

const props = defineProps<{ allocation: string }>()

const form = ref<ReviewForm | null>(null)
const loading = ref(true)
const error = ref("")
const ratings = ref<(number | null)[]>([])
const questionRemarks = ref<string[]>([])
const remarks = ref("")
const submitting = ref(false)

const done = computed(() => form.value?.status === "Completed")
const rated = computed(() => ratings.value.filter(Boolean).length)

async function load() {
	loading.value = true
	try {
		const data = await getReviewForm(props.allocation)
		form.value = data
		ratings.value = data.questions.map((_, index) => data.ratings[index] ?? null)
		questionRemarks.value = data.questions.map((_, index) => data.question_remarks[index] || "")
		remarks.value = data.remarks || ""
	} catch (e: any) {
		error.value = e?.messages?.[0] || ""
	} finally {
		loading.value = false
	}
}
load()

function confirmSubmit() {
	dialog.confirm({
		title: "Submit review",
		message: `Submit your review of ${form.value!.reviewee_name}? It cannot be changed afterwards.`,
		confirmLabel: "Submit",
		onConfirm: submit,
	})
}

async function submit() {
	submitting.value = true
	try {
		const answers = ratings.value.map((rating, index) => ({ rating: rating!, remarks: questionRemarks.value[index] || undefined }))
		await submitReview(props.allocation, answers, remarks.value)
		toast.success("Review submitted")
		await load()
	} finally {
		submitting.value = false
	}
}
</script>
