import { computed, ref, type Ref } from "vue"
import { deleteDoc, insertDoc, saveDoc } from "@/data/doc"
import { getList, type Filter } from "@/data/list"
import { can, loadPermissions } from "@/data/permissions"

/**
 * A short list of records of one DocType, edited one at a time in a dialog: load, add, change and
 * delete. The DocType's own validation and permissions decide what is allowed.
 */
export function useRecords<T extends Record<string, any>>(doctype: string, fields: string[], blank: () => Partial<T>) {
	const rows = ref([]) as Ref<T[]>
	const loading = ref(false)
	const saving = ref(false)
	// The record in the form; one without a name is new
	const editing = ref(null) as Ref<Partial<T> | null>
	const rights = computed(() => can(doctype))

	async function load(filters: Filter[] = []) {
		loading.value = true
		try {
			await loadPermissions([doctype])
			rows.value = await getList<T>({ doctype, fields: ["name", "modified", ...fields], filters, order_by: "creation asc", limit: 200 })
		} finally {
			loading.value = false
		}
	}

	const add = (values: Partial<T> = {}) => (editing.value = { ...blank(), ...values })
	const edit = (row: T) => (editing.value = { ...row })

	/** Saves the record in the form; the caller reloads the list. */
	async function save() {
		saving.value = true
		try {
			const doc = { doctype, ...editing.value }
			await (editing.value?.name ? saveDoc(doc) : insertDoc(doc))
			editing.value = null
		} finally {
			saving.value = false
		}
	}

	const remove = (row: T) => deleteDoc(doctype, row.name)

	return { rows, loading, saving, editing, rights, load, add, edit, save, remove }
}
