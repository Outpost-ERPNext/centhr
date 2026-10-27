import { computed, ref, shallowRef } from "vue"
import { useRoute, useRouter } from "vue-router"
import { dialog, toast } from "frappe-ui"
import {
	cancelDoc,
	deleteDoc,
	getWritableFields,
	insertDoc,
	loadDoc,
	missingRequired,
	newDoc,
	saveDoc,
	submitDoc,
	type DocInfo,
} from "./doc"
import { getMeta, loadMeta } from "./meta"
import { can, type Permissions } from "./permissions"
import { listRouteFor } from "@/utils/routes"

interface Options {
	/** Values for a new document, on top of the meta defaults (e.g. from the query string). */
	defaults?: () => Record<string, any>
	/** Called after a document loads or is created, to fetch page-specific extras. */
	onLoaded?: (doc: Record<string, any>) => void
	/** Fields required on top of the meta, checked before saving. */
	requiredFields?: () => string[]
}

/**
 * Loads one document for a detail page and wraps the standard lifecycle actions:
 * save, submit, cancel and delete. The server enforces permissions and validations;
 * the flags here only decide which buttons to show.
 */
export function useDocPage(doctype: string, name: string | null | undefined, options: Options = {}) {
	const router = useRouter()
	const route = useRoute()

	const doc = ref<Record<string, any>>({})
	const docinfo = shallowRef<DocInfo | null>(null)
	const permissions = ref<Permissions>(can(doctype))
	const writableFields = ref<string[]>([])
	const loading = ref(true)
	const busy = ref<string | null>(null)
	const notFound = ref<string | null>(null)
	const isNew = !name
	const editing = ref(isNew || route.query.edit === "1")
	let snapshot = ""

	const dirty = computed(() => editing.value && JSON.stringify(doc.value) !== snapshot)
	const isSubmittable = computed(() => !!getMeta(doctype)?.is_submittable)
	const docstatus = computed(() => doc.value.docstatus || 0)
	const canEdit = computed(() =>
		isNew ? permissions.value.create : permissions.value.write && (docstatus.value === 0 || hasAllowOnSubmit())
	)

	function hasAllowOnSubmit() {
		return docstatus.value === 1 && !!getMeta(doctype)?.fields.some((f) => f.allow_on_submit && !f.read_only && !f.hidden)
	}

	async function load() {
		loading.value = true
		notFound.value = null
		try {
			// Fresh on every page open, so fields added or deleted in Desk show without a hard reload
			await loadMeta(doctype, { refresh: true })
			writableFields.value = await getWritableFields(doctype, { refresh: true })
			if (isNew) {
				doc.value = newDoc(doctype, options.defaults?.() || {})
				permissions.value = can(doctype)
			} else {
				const res = await loadDoc(doctype, name!)
				doc.value = res.doc
				docinfo.value = res.docinfo
				permissions.value = res.permissions
			}
			snapshot = JSON.stringify(doc.value)
			options.onLoaded?.(doc.value)
		} catch (e: any) {
			notFound.value = e?.messages?.[0] || "This record could not be loaded"
		} finally {
			loading.value = false
		}
	}

	async function reload() {
		if (isNew) return
		const res = await loadDoc(doctype, name!)
		doc.value = res.doc
		docinfo.value = res.docinfo
		permissions.value = res.permissions
		snapshot = JSON.stringify(doc.value)
		options.onLoaded?.(doc.value)
	}

	function startEdit() {
		editing.value = true
		snapshot = JSON.stringify(doc.value)
	}

	function discard() {
		if (isNew) {
			router.push(listRouteFor(doctype) || "/")
			return
		}
		doc.value = JSON.parse(snapshot)
		editing.value = false
	}

	async function save() {
		const missing = missingRequired(doctype, doc.value, options.requiredFields?.() || [])
		if (missing.length) {
			toast.error(`Fill in the required fields: ${missing.join(", ")}`)
			return
		}
		busy.value = "save"
		try {
			const saved = isNew ? await insertDoc(doc.value) : await saveDoc(doc.value)
			toast.success(isNew ? `${doctype} created` : "Changes saved")
			editing.value = false
			if (isNew) {
				await router.replace(`${listRouteFor(doctype)}/${encodeURIComponent(saved.name)}`)
			} else {
				await reload()
			}
		} catch {
			// The api helper already showed the server's message
		} finally {
			busy.value = null
		}
	}

	function submit(confirmMessage?: string, values: Record<string, any> = {}) {
		dialog.confirm({
			title: `Submit ${doctype}`,
			message: confirmMessage || "Submitted records can no longer be edited. Continue?",
			confirmLabel: "Submit",
			onConfirm: async () => {
				busy.value = "submit"
				try {
					await submitDoc({ ...doc.value, ...values })
					toast.success(`${doctype} submitted`)
					await reload()
				} finally {
					busy.value = null
				}
			},
		})
	}

	function cancel() {
		dialog.confirm({
			title: `Cancel ${doctype}`,
			message: "Cancelling reverses this record's effects and cannot be undone. Continue?",
			confirmLabel: "Cancel record",
			cancelLabel: "Keep",
			theme: "red",
			onConfirm: async () => {
				busy.value = "cancel"
				try {
					await cancelDoc(doctype, doc.value.name)
					toast.success(`${doctype} cancelled`)
					await reload()
				} finally {
					busy.value = null
				}
			},
		})
	}

	function remove() {
		dialog.confirm({
			title: `Delete ${doctype}`,
			message: `Delete ${doc.value.name}? This cannot be undone.`,
			confirmLabel: "Delete",
			theme: "red",
			onConfirm: async () => {
				busy.value = "delete"
				try {
					await deleteDoc(doctype, doc.value.name)
					toast.success(`${doctype} deleted`)
					await router.push(listRouteFor(doctype) || "/")
				} finally {
					busy.value = null
				}
			},
		})
	}

	load()

	return {
		doc,
		docinfo,
		permissions,
		writableFields,
		loading,
		busy,
		notFound,
		isNew,
		editing,
		dirty,
		isSubmittable,
		docstatus,
		canEdit,
		load,
		reload,
		startEdit,
		discard,
		save,
		submit,
		cancel,
		remove,
	}
}
