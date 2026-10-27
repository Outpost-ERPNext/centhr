import { reactive } from "vue"
import { api } from "./api"

export interface DocField {
	fieldname: string
	fieldtype: string
	label?: string
	options?: string
	reqd?: 0 | 1
	read_only?: 0 | 1
	hidden?: 0 | 1
	default?: string
	depends_on?: string
	mandatory_depends_on?: string
	read_only_depends_on?: string
	in_list_view?: 0 | 1
	in_standard_filter?: 0 | 1
	allow_on_submit?: 0 | 1
	fetch_from?: string
	description?: string
	collapsible?: 0 | 1
	permlevel?: number
	idx?: number
}

export interface DocTypeMeta {
	name: string
	fields: DocField[]
	istable?: 0 | 1
	is_submittable?: 0 | 1
	title_field?: string
	image_field?: string
	autoname?: string
	sort_field?: string
	sort_order?: string
	search_fields?: string
}

export interface LayoutSection {
	label: string
	collapsible: boolean
	dependsOn?: string
	columns: DocField[][]
}

export interface LayoutTab {
	name: string
	label: string
	sections: LayoutSection[]
}

/** Field types that only shape the layout and never hold a value. */
export const LAYOUT_TYPES = ["Tab Break", "Section Break", "Column Break"]
export const NO_VALUE_TYPES = [...LAYOUT_TYPES, "HTML", "Button", "Image", "Fold", "Heading"]

const cache = reactive<Record<string, DocTypeMeta>>({})
const pending: Record<string, Promise<void>> = {}

/**
 * Loads a DocType's meta (with custom fields and property setters) and its child tables'.
 * `refresh` fetches it again, so fields added or deleted since the last load show up.
 */
export function loadMeta(doctype: string, { refresh = false }: { refresh?: boolean } = {}): Promise<void> {
	if (cache[doctype] && !refresh) return Promise.resolve()
	if (!pending[doctype]) {
		pending[doctype] = api<{ docs: DocTypeMeta[] }>("frappe.desk.form.load.getdoctype", { doctype })
			.then((res) => {
				for (const doc of res.docs) cache[doc.name] = doc
			})
			.finally(() => delete pending[doctype])
	}
	return pending[doctype]
}

export function getMeta(doctype: string): DocTypeMeta | undefined {
	return cache[doctype]
}

export function getField(doctype: string, fieldname: string): DocField | undefined {
	return cache[doctype]?.fields.find((f) => f.fieldname === fieldname)
}

export function fieldLabel(doctype: string, fieldname: string): string {
	return getField(doctype, fieldname)?.label || fieldname
}

export function selectOptions(doctype: string, fieldname: string): string[] {
	const options = getField(doctype, fieldname)?.options || ""
	return options.split("\n").filter((o) => o !== "")
}

/** Groups fields into tabs → sections → columns, the same way the Desk form does. */
export function getLayout(doctype: string): LayoutTab[] {
	const meta = cache[doctype]
	if (!meta) return []
	const tabs: LayoutTab[] = []
	let tab: LayoutTab = { name: "__details", label: "Details", sections: [] }
	let section: LayoutSection = newSection()
	let column: DocField[] = []

	const closeSection = () => {
		section.columns.push(column)
		section.columns = section.columns.filter((c) => c.length)
		if (section.columns.length) tab.sections.push(section)
		section = newSection()
		column = []
	}
	const closeTab = () => {
		closeSection()
		if (tab.sections.length) tabs.push(tab)
	}

	for (const field of meta.fields) {
		if (field.fieldtype === "Tab Break") {
			closeTab()
			tab = { name: field.fieldname, label: field.label || "Details", sections: [] }
		} else if (field.fieldtype === "Section Break") {
			closeSection()
			section = newSection(field)
		} else if (field.fieldtype === "Column Break") {
			section.columns.push(column)
			column = []
		} else {
			column.push(field)
		}
	}
	closeTab()
	return tabs
}

function newSection(field?: DocField): LayoutSection {
	return {
		label: field?.label || "",
		collapsible: !!field?.collapsible,
		dependsOn: field?.depends_on,
		columns: [],
	}
}
