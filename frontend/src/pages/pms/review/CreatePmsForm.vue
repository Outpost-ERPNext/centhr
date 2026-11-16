<template>
	<PageHeader :crumbs="[{ label: 'Create PMS Form' }]" />

	<div class="flex min-h-0 flex-1 flex-col overflow-y-auto">
		<QuarterScopeBar v-model="scope" company-required>
			<FilterLink v-model="designation" doctype="Designation" placeholder="All designations" />
		</QuarterScopeBar>

		<p class="px-5 text-[13px] text-ch-ink-3">
			Choose the questions for the quarter's 360 review. Every active employee of the chosen departments who has a submitted KPI Result in
			the quarter gets a questionnaire with them. Employees who have an open questionnaire get the questions they do not have yet.
		</p>

		<div class="grid grid-cols-1 gap-4 p-5 lg:grid-cols-2">
			<section class="flex min-w-0 flex-col gap-2 rounded-5 border border-ch-line bg-ch-surface p-4">
				<h2 class="text-[14px] font-medium text-ch-ink">Question bank</h2>
				<input
					v-model="search"
					type="search"
					placeholder="Search questions"
					aria-label="Search questions"
					class="h-8 rounded-3 border-0 bg-ch-subtle px-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4"
				/>
				<ul class="flex max-h-[420px] flex-col overflow-y-auto">
					<li v-for="question in shownBank" :key="question.name">
						<label class="flex cursor-pointer items-start gap-2 rounded-3 px-1 py-1.5 text-[13px] hover:bg-ch-hover">
							<Checkbox :model-value="isChosen(question.question)" @update:model-value="toggle(question.question)" />
							<span class="min-w-0">
								<span class="text-ch-ink">{{ question.question }}</span>
								<span class="block text-[12px] text-ch-ink-3">
									{{ question.is_a_general_question ? "Everyone" : [question.department, question.designation].filter(Boolean).join(" · ") }}
								</span>
							</span>
						</label>
					</li>
					<li v-if="!shownBank.length" class="py-6 text-center text-[13px] text-ch-ink-3">No questions in the bank match</li>
				</ul>
				<div class="flex gap-2 border-t border-ch-line pt-3">
					<input
						v-model="custom"
						type="text"
						placeholder="Or type a question of your own"
						aria-label="Your own question"
						class="h-8 min-w-0 flex-1 rounded-3 border-0 bg-ch-subtle px-2 text-[13px] text-ch-ink placeholder:text-ch-ink-4"
						@keydown.enter="addCustom"
					/>
					<Button label="Add" :disabled="!custom.trim()" @click="addCustom" />
				</div>
			</section>

			<section class="flex min-w-0 flex-col gap-2 rounded-5 border border-ch-line bg-ch-surface p-4">
				<h2 class="text-[14px] font-medium text-ch-ink">Questions to ask ({{ chosen.length }})</h2>
				<ol class="flex flex-col gap-2">
					<li v-for="(question, index) in chosen" :key="question.question" class="flex items-start gap-2 text-[13px]">
						<span class="w-5 shrink-0 pt-1.5 text-right tabular-nums text-ch-ink-3">{{ index + 1 }}</span>
						<span class="min-w-0 flex-1 pt-1.5 text-ch-ink">{{ question.question }}</span>
						<div class="w-40 shrink-0">
							<LinkField v-model="question.question_trait" doctype="PMS Question Trait" placeholder="Trait" size="sm" />
						</div>
						<Button variant="ghost" icon="lucide-x" aria-label="Remove question" @click="toggle(question.question)" />
					</li>
					<li v-if="!chosen.length" class="py-6 text-center text-ch-ink-3">Tick questions in the bank, or add your own</li>
				</ol>
				<div class="mt-auto flex flex-wrap items-center justify-end gap-2 border-t border-ch-line pt-3">
					<span v-if="!scope.company" class="mr-auto text-[12px] text-ch-ink-3">Choose a company first</span>
					<Button label="Check who gets them" :disabled="!canRun" :loading="busy === 'preview'" @click="run(true)" />
					<Button variant="solid" label="Create questionnaires" :disabled="!canRun" :loading="busy === 'create'" @click="confirmCreate" />
				</div>
			</section>
		</div>

		<section v-if="outcome" class="mx-5 mb-5 rounded-5 border border-ch-line bg-ch-surface p-4 text-[13px]">
			<h2 class="text-[14px] font-medium text-ch-ink">{{ outcomeTitle }}</h2>
			<p class="mt-1 text-ch-ink-2">
				{{ outcome.created.length }} new questionnaires, {{ outcome.updated.length }} open ones updated, {{ outcome.skipped.length }} employees
				skipped.
			</p>
			<table v-if="outcome.skipped.length" class="mt-3 w-full text-left">
				<thead class="text-ch-ink-3">
					<tr>
						<th class="py-1 font-normal">Skipped employee</th>
						<th class="py-1 font-normal">Why</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in outcome.skipped" :key="row.employee" class="border-t border-ch-line">
						<td class="py-1.5 text-ch-ink">{{ row.employee_name }} <span class="text-ch-ink-3">{{ row.employee }}</span></td>
						<td class="py-1.5 text-ch-ink-2">{{ row.reason }}</td>
					</tr>
				</tbody>
			</table>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Checkbox, dialog, toast } from "frappe-ui"
import PageHeader from "@/components/layout/PageHeader.vue"
import FilterLink from "@/components/FilterLink.vue"
import LinkField from "@/components/fields/LinkField.vue"
import QuarterScopeBar from "./QuarterScopeBar.vue"
import { getList } from "@/data/list"
import { createQuestionnaires, type BuildOutcome, type FormQuestion, type QuarterScope } from "@/data/pmsReview"

interface BankQuestion {
	name: string
	question: string
	is_a_general_question: 0 | 1
	department: string | null
	designation: string | null
}

const scope = ref<QuarterScope>({ fiscalYear: "", quarter: "", company: "", department: "" })
const designation = ref("")
const search = ref("")
const custom = ref("")
const bank = ref<BankQuestion[]>([])
const chosen = ref<FormQuestion[]>([])
const outcome = ref<BuildOutcome | null>(null)
const wasPreview = ref(false)
const busy = ref<"preview" | "create" | null>(null)

getList<BankQuestion>({
	doctype: "PMS Question",
	fields: ["name", "question", "is_a_general_question", "department", "designation"],
	order_by: "is_a_general_question desc, creation asc",
	limit: 0,
}).then((rows) => (bank.value = rows))

/** General questions, and the ones of the chosen department or designation. */
const shownBank = computed(() => {
	const text = search.value.trim().toLowerCase()
	return bank.value.filter(
		(q) =>
			(!text || q.question.toLowerCase().includes(text)) &&
			(q.is_a_general_question ||
				((!scope.value.department || !q.department || q.department === scope.value.department) &&
					(!designation.value || !q.designation || q.designation === designation.value)))
	)
})

const isChosen = (question: string) => chosen.value.some((q) => q.question === question)

function toggle(question: string) {
	chosen.value = isChosen(question) ? chosen.value.filter((q) => q.question !== question) : [...chosen.value, { question, question_trait: null }]
}

function addCustom() {
	const question = custom.value.trim()
	if (question && !isChosen(question)) toggle(question)
	custom.value = ""
}

const canRun = computed(() => !!scope.value.company && !!scope.value.fiscalYear && chosen.value.length > 0 && !busy.value)
const outcomeTitle = computed(() => (wasPreview.value ? "What would happen" : "Done"))

function confirmCreate() {
	dialog.confirm({
		title: "Create questionnaires",
		message: `Give these ${chosen.value.length} questions to the eligible employees of ${scope.value.department || scope.value.company} for ${scope.value.quarter} ${scope.value.fiscalYear}?`,
		confirmLabel: "Create",
		onConfirm: () => run(false),
	})
}

async function run(preview: boolean) {
	busy.value = preview ? "preview" : "create"
	try {
		outcome.value = await createQuestionnaires(scope.value, chosen.value, designation.value, preview)
		wasPreview.value = preview
		if (!preview) toast.success(`${outcome.value.created.length} questionnaires created, ${outcome.value.updated.length} updated`)
	} finally {
		busy.value = null
	}
}
</script>
