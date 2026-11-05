import { computed, reactive, ref, watch } from "vue"
import { useRoute, useRouter, type LocationQuery } from "vue-router"
import { STRUCTURE_VIEWS, TILES, compareRows, countBy, getSalaryOverview, type SalaryRow } from "@/data/salaryOverview"
import { readStorage, writeStorage } from "@/utils/storage"

const DEFAULTS = {
	company: "",
	from: "",
	to: "",
	tile: "active",
	view: "all",
	search: "",
	department: "",
	structure: "",
	employee: "",
	sort: "name",
	order: "asc" as "asc" | "desc",
	page: 1,
	pageSize: 20,
}
type State = typeof DEFAULTS
const FILTER_KEYS = ["company", "tile", "view", "search", "department", "structure", "employee", "pageSize"] as const

/**
 * Employees in one payroll period, with the tiles, chips, filters, sort and paging of the salary overview pages.
 * The whole view lives in the URL, so Back restores it; the last view of each page is also kept for the next visit.
 */
export function useSalaryOverview(page: string) {
	const route = useRoute()
	const router = useRouter()
	const storageKey = `centhr-salary-overview-${page}`

	const state = reactive<State>(readState(Object.keys(route.query).length ? route.query : storedQuery(storageKey)))
	const rows = ref<SalaryRow[]>([])
	const loading = ref(false)
	const error = ref<string | null>(null)

	const tileCounts = computed(() => countBy(TILES, rows.value, state))
	// The chips count within the selected tile, so they add up to what the table can show
	const tileRows = computed(() => rows.value.filter((r) => findTest(TILES, state.tile)(r, state)))
	const viewCounts = computed(() => countBy(STRUCTURE_VIEWS, tileRows.value, state))

	const filtered = computed(() => {
		const viewTest = findTest(STRUCTURE_VIEWS, state.view)
		const term = state.search.trim().toLowerCase()
		return tileRows.value
			.filter((r) => viewTest(r, state))
			.filter((r) => !term || r.name.toLowerCase().includes(term) || r.employee_name.toLowerCase().includes(term))
			.filter((r) => !state.department || r.department === state.department)
			.filter((r) => !state.structure || r.salary_structure === state.structure)
			.filter((r) => !state.employee || r.name === state.employee)
			.sort((a, b) => compareRows(a, b, state.sort) * (state.order === "asc" ? 1 : -1))
	})
	const pageRows = computed(() => filtered.value.slice((state.page - 1) * state.pageSize, state.page * state.pageSize))
	const hasFilters = computed(() => !!(state.search || state.department || state.structure || state.employee || state.view !== "all"))

	watch(
		() => FILTER_KEYS.map((key) => state[key]).join("|"),
		() => (state.page = 1)
	)
	watch(() => ({ ...state }), persist, { deep: true })
	watch([() => state.company, () => state.from, () => state.to], load)
	// Declared before the first load below, which uses it straight away
	let requestId = 0
	persist()
	load()

	async function load() {
		if (!state.from || !state.to) return
		const id = ++requestId
		loading.value = true
		error.value = null
		try {
			const result = await getSalaryOverview(state.company, state)
			// A slower, older request must not overwrite a newer one
			if (id === requestId) rows.value = result
		} catch (e: any) {
			if (id === requestId) error.value = e?.messages?.[0] || e?.message || "Could not load employees"
		} finally {
			if (id === requestId) loading.value = false
		}
	}

	function persist() {
		const query = Object.fromEntries(
			Object.entries(state)
				.filter(([key, value]) => value !== DEFAULTS[key as keyof State])
				.map(([key, value]) => [key, String(value)])
		)
		// Keys the page itself keeps in the URL (such as the dashboard tab) stay as they are
		const others = Object.fromEntries(Object.entries(route.query).filter(([key]) => !(key in DEFAULTS)))
		router.replace({ query: { ...others, ...query } })
		writeStorage(storageKey, JSON.stringify(query))
	}

	function clearFilters() {
		Object.assign(state, { search: "", department: "", structure: "", employee: "", view: "all" })
	}

	function toggleSort(field: string) {
		state.order = state.sort === field && state.order === "asc" ? "desc" : "asc"
		state.sort = field
	}

	return { state, rows, loading, error, tileCounts, viewCounts, filtered, pageRows, hasFilters, load, clearFilters, toggleSort }
}

export type SalaryOverview = ReturnType<typeof useSalaryOverview>

function readState(query: LocationQuery | Record<string, string>): State {
	const value = (key: keyof State) => (typeof query[key] === "string" ? (query[key] as string) : undefined)
	return {
		...DEFAULTS,
		...Object.fromEntries(Object.keys(DEFAULTS).flatMap((key) => (value(key as keyof State) ? [[key, value(key as keyof State)]] : []))),
		order: value("order") === "desc" ? "desc" : "asc",
		page: Math.max(1, Number(value("page")) || 1),
		pageSize: Number(value("pageSize")) || DEFAULTS.pageSize,
	}
}

function storedQuery(key: string): Record<string, string> {
	try {
		return JSON.parse(readStorage(key, "{}"))
	} catch {
		return {}
	}
}

function findTest<T extends { key: string; test: any }>(filters: T[], key: string): T["test"] {
	return (filters.find((f) => f.key === key) || filters[0]).test
}
