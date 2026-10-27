import { api } from "./api"
import { getMeta, loadMeta, NO_VALUE_TYPES } from "./meta"
import { session } from "./session"
import { evaluateDependsOn, isRequired } from "@/utils/dependsOn"
import { nowDatetime, today } from "@/utils/format"
import type { Permissions } from "./permissions"

export interface DocInfo {
	permissions: Record<string, 0 | 1>
	comments: { name: string; content: string; owner: string; creation: string; comment_type?: string }[]
	versions: { name: string; owner: string; creation: string; data: string }[]
	attachments: { name: string; file_name: string; file_url: string }[]
}

/** Loads a document with its timeline and the session user's permissions on it. */
export async function loadDoc(doctype: string, name: string) {
	await loadMeta(doctype)
	const res = await api<{ docs: Record<string, any>[]; docinfo: DocInfo }>("frappe.desk.form.load.getdoc", {
		doctype,
		name,
	})
	const p = res.docinfo?.permissions || {}
	const permissions: Permissions = {
		read: !!p.read,
		write: !!p.write,
		create: !!p.create,
		submit: !!p.submit,
		cancel: !!p.cancel,
		delete: !!p.delete,
	}
	return { doc: res.docs[0], docinfo: res.docinfo, permissions }
}

/** A new document with the defaults from its meta, like a new Desk form. */
export function newDoc(doctype: string, values: Record<string, any> = {}) {
	const meta = getMeta(doctype)
	// __islocal marks an unsaved doc, which some depends_on expressions check
	const doc: Record<string, any> = { doctype, docstatus: 0, __islocal: 1 }
	for (const field of meta?.fields || []) {
		if (NO_VALUE_TYPES.includes(field.fieldtype)) continue
		if (field.fieldtype === "Table") {
			doc[field.fieldname] = []
			continue
		}
		const value = resolveDefault(field.default, field.fieldtype)
		if (value !== undefined) doc[field.fieldname] = value
		else if (field.fieldtype === "Select" && field.reqd && field.options) {
			doc[field.fieldname] = field.options.split("\n").find(Boolean)
		}
		if (field.fieldname === "naming_series" && !doc.naming_series && field.options) {
			doc.naming_series = field.options.split("\n").find(Boolean)
		}
	}
	return Object.assign(doc, values)
}

function resolveDefault(value: string | undefined, fieldtype: string) {
	if (value === undefined || value === null || value === "") return undefined
	const lower = String(value).toLowerCase()
	if (lower === "today") return today()
	if (lower === "now") return fieldtype === "Datetime" ? nowDatetime() : undefined
	if (value === "__user") return session.user
	if (["Int", "Check"].includes(fieldtype)) return parseInt(value, 10)
	if (["Float", "Currency", "Percent"].includes(fieldtype)) return parseFloat(value)
	return value
}

/** A new document of a DocType named by the user ("prompt"), whose name goes in `__newname`. */
export function needsPromptName(doctype: string, doc: Record<string, any>): boolean {
	return !!doc.__islocal && !!getMeta(doctype)?.autoname?.toLowerCase().startsWith("prompt")
}

/** Labels of required fields that are visible and still empty. */
export function missingRequired(doctype: string, doc: Record<string, any>, extra: string[] = []): string[] {
	const missing: string[] = []
	if (needsPromptName(doctype, doc) && !String(doc.__newname || "").trim()) missing.push("Name")
	for (const field of getMeta(doctype)?.fields || []) {
		if (NO_VALUE_TYPES.includes(field.fieldtype) || field.read_only) continue
		if (field.hidden || !evaluateDependsOn(field.depends_on, doc)) continue
		if (!isRequired(field, doc) && !extra.includes(field.fieldname)) continue
		const value = doc[field.fieldname]
		const empty = value === null || value === undefined || value === "" || (Array.isArray(value) && !value.length)
		if (empty) missing.push(field.label || field.fieldname)
	}
	return missing
}

export const insertDoc = (doc: Record<string, any>) => api<Record<string, any>>("frappe.client.insert", { doc })
export const saveDoc = (doc: Record<string, any>) => api<Record<string, any>>("frappe.client.save", { doc })
export const submitDoc = (doc: Record<string, any>) => api<Record<string, any>>("frappe.client.submit", { doc })
export const cancelDoc = (doctype: string, name: string) =>
	api<Record<string, any>>("frappe.client.cancel", { doctype, name })
export const deleteDoc = (doctype: string, name: string) => api("frappe.client.delete", { doctype, name })

export const addComment = (doctype: string, name: string, content: string) =>
	api("frappe.desk.form.utils.add_comment", {
		reference_doctype: doctype,
		reference_name: name,
		content,
		comment_email: session.user,
		comment_by: session.fullName || session.user,
	})

const writeFieldsCache: Record<string, Promise<string[]>> = {}

/** Fields the session user may write, after field-level (permlevel) permissions. */
export function getWritableFields(doctype: string, { refresh = false }: { refresh?: boolean } = {}): Promise<string[]> {
	if (!writeFieldsCache[doctype] || refresh) {
		writeFieldsCache[doctype] = api<string[]>("hrms.api.get_permitted_fields_for_write", { doctype }).catch(
			() => []
		)
	}
	return writeFieldsCache[doctype]
}
