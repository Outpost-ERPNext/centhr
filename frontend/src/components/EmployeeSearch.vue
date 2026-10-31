<template>
	<div class="relative w-full sm:w-56">
		<span class="lucide-search pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-ch-ink-3" />
		<input
			:value="text"
			type="text"
			role="combobox"
			:placeholder="placeholder"
			:aria-label="placeholder"
			:aria-expanded="open"
			aria-autocomplete="list"
			autocomplete="off"
			class="h-7 w-full rounded-3 border-0 bg-ch-subtle pl-7 pr-6 text-[13px] text-ch-ink placeholder:text-ch-ink-4 focus:ring-2 focus:ring-[var(--ch-line-2)]"
			@input="onInput(($event.target as HTMLInputElement).value)"
			@focus="text.trim() && suggest(text)"
			@blur="open = false"
			@keydown.down.prevent="move(1)"
			@keydown.up.prevent="move(-1)"
			@keydown.enter.prevent="active >= 0 && pick(suggestions[active])"
			@keydown.esc="open = false"
		/>
		<button
			v-if="text"
			type="button"
			class="absolute right-1.5 top-1/2 flex -translate-y-1/2 text-ch-ink-3 hover:text-ch-ink"
			:aria-label="`Clear ${placeholder}`"
			@click="clear"
		>
			<span class="lucide-x size-3.5" />
		</button>

		<ul
			v-if="open && text.trim()"
			role="listbox"
			class="absolute left-0 top-8 z-20 max-h-72 w-full min-w-[260px] overflow-y-auto rounded-4 border border-ch-line bg-ch-surface py-1 shadow-ch-card"
		>
			<li v-if="!suggestions.length" class="px-3 py-2 text-[13px] text-ch-ink-3">
				{{ loading ? "Searching…" : "No employees found" }}
			</li>
			<li
				v-for="(emp, i) in suggestions"
				:key="emp.name"
				role="option"
				:aria-selected="i === active"
				class="flex cursor-pointer flex-col px-3 py-1.5 text-[13px]"
				:class="i === active ? 'bg-ch-hover' : 'hover:bg-ch-hover'"
				@mousedown.prevent="pick(emp)"
				@mouseenter="active = i"
			>
				<span class="truncate font-medium text-ch-ink">{{ emp.employee_name }}</span>
				<span class="truncate text-[12px] text-ch-ink-3">
					{{ emp.name }}<template v-if="emp.employee_number && emp.employee_number !== emp.name"> · {{ emp.employee_number }}</template>
					<template v-if="emp.department"> · {{ emp.department }}</template>
				</span>
			</li>
		</ul>
	</div>
</template>

<script setup lang="ts">
import { ref, watch } from "vue"
import { getList, type Filter } from "@/data/list"

interface Suggestion {
	name: string
	employee_name: string
	employee_number?: string
	department?: string
}

const props = defineProps<{
	placeholder: string
	company?: string | null
	/** Suggest only Active employees, for views that list only those. */
	activeOnly?: boolean
}>()
const emit = defineEmits<{ select: [employee: string] }>()
/** The typed text; the page filters by it. Picking a suggestion sets it to that employee's ID. */
const model = defineModel<string>({ default: "" })

const text = ref(model.value || "")
watch(model, (v) => {
	if ((v || "") !== text.value.trim()) text.value = v || ""
})

const suggestions = ref<Suggestion[]>([])
const open = ref(false)
const active = ref(-1)
const loading = ref(false)

// What is typed shows at once; the model and the suggestions follow after a pause
let timer: ReturnType<typeof setTimeout> | undefined
function onInput(value: string) {
	text.value = value
	clearTimeout(timer)
	timer = setTimeout(() => {
		model.value = value.trim()
		suggest(value)
	}, 250)
}

let requestId = 0
/** Employees of the company whose name, ID or Employee Number contains the text. */
async function suggest(value: string) {
	const query = value.trim()
	const id = ++requestId
	open.value = !!query
	active.value = -1
	if (!query) return (suggestions.value = [])
	loading.value = true
	const like = `%${query}%`
	const filters: Filter[] = props.company ? [["company", "=", props.company]] : []
	if (props.activeOnly) filters.push(["status", "=", "Active"])
	try {
		const rows = await getList<Suggestion>({
			doctype: "Employee",
			fields: ["name", "employee_name", "employee_number", "department"],
			filters,
			or_filters: [
				["employee_name", "like", like],
				["name", "like", like],
				["employee_number", "like", like],
			],
			order_by: "employee_name asc",
			limit: 10,
			silent: true,
		})
		if (id === requestId) suggestions.value = rows
	} catch {
		if (id === requestId) suggestions.value = []
	} finally {
		if (id === requestId) loading.value = false
	}
}

// Suggestions from another company must not stay open
watch(
	() => props.company,
	() => (suggestions.value = [])
)

function move(step: number) {
	if (!open.value || !suggestions.value.length) return
	active.value = (active.value + step + suggestions.value.length) % suggestions.value.length
}

function pick(emp: Suggestion | undefined) {
	if (!emp) return
	clearTimeout(timer)
	open.value = false
	text.value = emp.name
	emit("select", emp.name)
	model.value = emp.name
}

function clear() {
	clearTimeout(timer)
	text.value = ""
	suggestions.value = []
	open.value = false
	model.value = ""
}
</script>
