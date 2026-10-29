import { computed, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { getList } from "@/data/list"
import { STRUCTURE_VIEWS, TILES, compareRows, countBy, getSalaryOverview, type SalaryRow } from "@/data/salaryOverview"

/**
 * Employees of one company in one payroll period, with the tiles, chips, filters, sort and paging
 * of the salary overview pages. Company and period live in the URL, so a refresh keeps the view.
 */
export function useSalaryOverview() {
	const route = useRoute()
	const router = useRouter()

	const company = ref((route.query.company as string) || "")
	const period = reactive({ from: (route.query.from as string) || "", to: (route.query.to as string) || "" })

	const rows = ref<SalaryRow[]>([])
	const loading = ref(false)
	const error = ref<string | null>(null)

	const tile = ref("active")
	const view = ref("all")
	const search = ref("")
	const department = ref("")
	const structure = ref("")
	const sort = reactive({ field: "name", order: "asc" as "asc" | "desc" })
	const page = ref(1)
	const pageSize = ref(20)

	const tileCounts = computed(() => countBy(TILES, rows.value, period))
	// The chips count within the selected tile, so they add up to what the table can show
	const tileRows = computed(() => rows.value.filter((r) => findTest(TILES, tile.value)(r, period)))
	const viewCounts = computed(() => countBy(STRUCTURE_VIEWS, tileRows.value, period))

	const filtered = computed(() => {
		const viewTest = findTest(STRUCTURE_VIEWS, view.value)
		const term = search.value.trim().toLowerCase()
		return tileRows.value
			.filter((r) => viewTest(r, period))
			.filter((r) => !term || r.name.toLowerCase().includes(term) || r.employee_name.toLowerCase().includes(term))
			.filter((r) => !department.value || r.department === department.value)
			.filter((r) => !structure.value || r.salary_structure === structure.value)
			.sort((a, b) => compareRows(a, b, sort.field) * (sort.order === "asc" ? 1 : -1))
	})
	const pageRows = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
	const hasFilters = computed(() => !!(search.value || department.value || structure.value || view.value !== "all"))

	watch([tile, view, search, department, structure, pageSize], () => (page.value = 1))
	watch([company, () => period.from, () => period.to], () => {
		router.replace({
			query: { ...route.query, company: company.value || undefined, from: period.from || undefined, to: period.to || undefined },
		})
		load()
	})
	if (company.value) load()
	else setDefaultCompany()

	let requestId = 0
	async function load() {
		if (!company.value || !period.from || !period.to) return
		const id = ++requestId
		loading.value = true
		error.value = null
		try {
			const result = await getSalaryOverview(company.value, period)
			// A slower, older request must not overwrite a newer one
			if (id === requestId) rows.value = result
		} catch (e: any) {
			if (id === requestId) error.value = e?.messages?.[0] || e?.message || "Could not load employees"
		} finally {
			if (id === requestId) loading.value = false
		}
	}

	function setCompany(value: string) {
		company.value = value
		rows.value = []
		clearFilters()
	}

	/** Opens on the first company the user can see. */
	async function setDefaultCompany() {
		const [first] = await getList({ doctype: "Company", fields: ["name"], order_by: "name asc", limit: 1, silent: true }).catch(() => [])
		if (first && !company.value) company.value = first.name
	}

	function clearFilters() {
		search.value = department.value = structure.value = ""
		view.value = "all"
	}

	function toggleSort(field: string) {
		sort.order = sort.field === field && sort.order === "asc" ? "desc" : "asc"
		sort.field = field
	}

	return {
		company,
		period,
		rows,
		loading,
		error,
		tile,
		view,
		search,
		department,
		structure,
		sort,
		page,
		pageSize,
		tileCounts,
		viewCounts,
		filtered,
		pageRows,
		hasFilters,
		load,
		setCompany,
		clearFilters,
		toggleSort,
	}
}

export type SalaryOverview = ReturnType<typeof useSalaryOverview>

function findTest<T extends { key: string; test: any }>(filters: T[], key: string): T["test"] {
	return (filters.find((f) => f.key === key) || filters[0]).test
}
