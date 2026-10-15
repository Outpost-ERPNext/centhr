import { reactive } from "vue"
import { api } from "./api"

export interface Permissions {
	read: boolean
	write: boolean
	create: boolean
	submit: boolean
	cancel: boolean
	delete: boolean
}

const NONE: Permissions = { read: false, write: false, create: false, submit: false, cancel: false, delete: false }
const cache = reactive<Record<string, Permissions>>({})

/** DocType-level permissions for the session user. Only for showing or hiding actions. */
export async function loadPermissions(doctypes: string[]) {
	const missing = doctypes.filter((d) => !cache[d])
	if (!missing.length) return
	const res = await api<Record<string, Permissions>>("centhr.api.permission.get_doctype_permissions", {
		doctypes: missing,
	})
	Object.assign(cache, res)
}

export function can(doctype: string): Permissions {
	return cache[doctype] || NONE
}

const readableCache: Record<string, Promise<string[]>> = {}

/** Fields the session user may read after field-level (permlevel) permissions. */
export function getReadableFields(doctype: string): Promise<string[]> {
	if (!readableCache[doctype]) {
		readableCache[doctype] = api<string[]>("centhr.api.permission.get_readable_fields", { doctype }, { silent: true }).catch(
			() => []
		)
	}
	return readableCache[doctype]
}

/** Permissions for one document, after user permissions and sharing are applied. */
export async function getDocPermissions(doctype: string, name: string): Promise<Permissions> {
	const res = await api<{ permissions: Record<string, 0 | 1> }>("frappe.client.get_doc_permissions", {
		doctype,
		docname: name,
	})
	const p = res.permissions || {}
	return {
		read: !!p.read,
		write: !!p.write,
		create: !!p.create,
		submit: !!p.submit,
		cancel: !!p.cancel,
		delete: !!p.delete,
	}
}
