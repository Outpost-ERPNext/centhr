import { reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { api } from "./api"

export type Filter = [string, string, any]

/** Runs a permission-checked list query through `frappe.client.get_list`. */
export function getList<T = Record<string, any>>(args: {
	doctype: string
	fields: (string | Record<string, string>)[]
	filters?: Filter[]
	or_filters?: Filter[]
	order_by?: string
	group_by?: string
	start?: number
	limit?: number
	/** Do not toast errors; for optional widgets that the user may not have access to. */
	silent?: boolean
}) {
	return api<T[]>(
		"frappe.client.get_list",
		{
		doctype: args.doctype,
		fields: args.fields,
		filters: args.filters || [],
		or_filters: args.or_filters || [],
		order_by: args.order_by,
		group_by: args.group_by,
		limit_start: args.start || 0,
		limit_page_length: args.limit ?? 20,
		},
		{ silent: args.silent }
	)
}

export async function getCount(doctype: string, filters: Filter[] = [], or_filters: Filter[] = [], silent = false) {
	const rows = await getList<{ count: number }>({
		doctype,
		fields: [{ COUNT: "*", as: "count" }],
		filters,
		or_filters,
		limit: 1,
		silent,
	})
	return rows[0]?.count || 0
}

/** Counts per value of one field, for example Leave Applications per status. */
export async function getGroupCounts(doctype: string, field: string, filters: Filter[] = [], silent = true) {
	const rows = await getList<Record<string, any>>({
		doctype,
		fields: [field, { COUNT: "*", as: "count" }],
		filters,
		group_by: field,
		limit: 0,
		silent,
	})
	return Object.fromEntries(rows.map((r) => [r[field], r.count])) as Record<string, number>
}

export interface ListState {
	search: string
	filters: Record<string, string>
	sortField: string
	sortOrder: "asc" | "desc"
	page: number
	pageSize: number
}

interface DocListOptions {
	doctype: string
	/** A function when the fields depend on something loaded first (see `ready`). */
	fields: string[] | (() => string[])
	/** Awaited before the first query, for example field permissions. */
	ready?: Promise<unknown>
	/** Fields searched with LIKE when the user types in the search box. */
	searchFields: string[]
	defaultSort: { field: string; order: "asc" | "desc" }
	/** Turns the UI filter values into query filters; async when a filter needs a lookup first. */
	buildFilters: (state: ListState) => Filter[] | Promise<Filter[]>
	pageSize?: number
}

const QUERY_KEYS = ["q", "sort", "order", "page", "size"]

/**
 * A paginated, sorted and filtered list. Its state lives in the URL query, so a
 * refresh or a shared link shows the same page.
 */
export function useDocList<T = Record<string, any>>(options: DocListOptions) {
	const route = useRoute()
	const router = useRouter()

	const state = reactive<ListState>({
		search: "",
		filters: {},
		sortField: options.defaultSort.field,
		sortOrder: options.defaultSort.order,
		page: 1,
		pageSize: options.pageSize || 20,
	})
	readQuery()

	const rows = ref<T[]>([]) as { value: T[] }
	const total = ref(0)
	const loading = ref(false)
	const error = ref<string | null>(null)
	let requestId = 0

	async function reload() {
		const id = ++requestId
		loading.value = true
		error.value = null
		await options.ready
		if (id !== requestId) return
		const or_filters: Filter[] = state.search.trim()
			? options.searchFields.map((f) => [f, "like", `%${state.search.trim()}%`])
			: []
		try {
			const filters = await options.buildFilters(state)
			if (id !== requestId) return
			const [data, count] = await Promise.all([
				getList<T>({
					doctype: options.doctype,
					fields: typeof options.fields === "function" ? options.fields() : options.fields,
					filters,
					or_filters,
					order_by: `${state.sortField} ${state.sortOrder}`,
					start: (state.page - 1) * state.pageSize,
					limit: state.pageSize,
				}),
				getCount(options.doctype, filters, or_filters),
			])
			// A slower, older request must not overwrite a newer one
			if (id !== requestId) return
			rows.value = data
			total.value = count
		} catch (e: any) {
			if (id === requestId) error.value = e?.messages?.[0] || e?.message || "Could not load records"
		} finally {
			if (id === requestId) loading.value = false
		}
	}

	function readQuery() {
		const q = route.query
		state.search = (q.q as string) || ""
		state.sortField = (q.sort as string) || options.defaultSort.field
		state.sortOrder = q.order === "asc" || q.order === "desc" ? q.order : options.defaultSort.order
		state.page = Math.max(1, Number(q.page) || 1)
		state.pageSize = Number(q.size) || options.pageSize || 20
		const filters: Record<string, string> = {}
		for (const [key, value] of Object.entries(q)) {
			if (!QUERY_KEYS.includes(key) && typeof value === "string") filters[key] = value
		}
		state.filters = filters
	}

	function writeQuery() {
		const query: Record<string, string> = {}
		for (const [key, value] of Object.entries(state.filters)) {
			if (value !== "" && value !== null && value !== undefined) query[key] = value
		}
		if (state.search) query.q = state.search
		if (state.sortField !== options.defaultSort.field) query.sort = state.sortField
		if (state.sortOrder !== options.defaultSort.order) query.order = state.sortOrder
		if (state.page > 1) query.page = String(state.page)
		if (state.pageSize !== (options.pageSize || 20)) query.size = String(state.pageSize)
		router.replace({ query })
	}

	let searchTimer: ReturnType<typeof setTimeout> | undefined
	let resettingPage = false
	watch(
		() => [state.search, JSON.stringify(state.filters), state.sortField, state.sortOrder, state.pageSize],
		(now, before) => {
			// Any change other than the page sends the user back to page 1
			if (state.page !== 1) {
				resettingPage = true
				state.page = 1
			}
			clearTimeout(searchTimer)
			const searchChanged = now[0] !== before[0]
			searchTimer = setTimeout(
				() => {
					writeQuery()
					reload()
				},
				searchChanged ? 300 : 0
			)
		}
	)
	watch(
		() => state.page,
		() => {
			if (resettingPage) {
				resettingPage = false
				return
			}
			writeQuery()
			reload()
		}
	)

	function toggleSort(field: string) {
		if (state.sortField === field) {
			state.sortOrder = state.sortOrder === "asc" ? "desc" : "asc"
		} else {
			state.sortField = field
			state.sortOrder = "asc"
		}
	}

	function clearFilters() {
		state.search = ""
		state.filters = {}
	}

	reload()
	return { state, rows, total, loading, error, reload, toggleSort, clearFilters }
}

/** Turns a date operator filter ("between", "=", "<=", ">=") into a query filter. */
export function dateFilter(field: string, op: string | undefined, from: string | undefined, to?: string): Filter | null {
	if (!op || !from) return null
	if (op === "between") return to ? [field, "between", [from, to]] : [field, ">=", from]
	return [field, op, from]
}
