import type { DocField } from "@/data/meta"
import { hasRole, session } from "@/data/session"

/**
 * Evaluates a `depends_on` style expression the way the Desk form does:
 * `eval:<js expression>` with `doc` in scope, or a bare fieldname that must be truthy.
 * Expressions come from DocType metadata, which only System Managers can edit.
 */
export function evaluateDependsOn(expression: string | undefined, doc: Record<string, any>): boolean {
	if (!expression) return true
	const expr = expression.trim()
	if (expr.startsWith("eval:")) {
		try {
			// eslint-disable-next-line no-new-func
			const fn = new Function(...Object.keys(GLOBALS), "doc", "parent", `return (${expr.slice(5).trim().replace(/;+$/, "")})`)
			return !!fn(...Object.values(GLOBALS), doc, doc)
		} catch {
			return true
		}
	}
	const value = doc[expr]
	return Array.isArray(value) ? value.length > 0 : !!value
}

export function isVisible(field: DocField, doc: Record<string, any>) {
	return !field.hidden && evaluateDependsOn(field.depends_on, doc)
}

export function isRequired(field: DocField, doc: Record<string, any>) {
	if (field.reqd) return true
	return field.mandatory_depends_on ? evaluateDependsOn(field.mandatory_depends_on, doc) : false
}

export function isReadOnly(field: DocField, doc: Record<string, any>) {
	if (field.read_only) return true
	if (doc.docstatus === 1 && !field.allow_on_submit) return true
	if (doc.docstatus === 2) return true
	return field.read_only_depends_on ? evaluateDependsOn(field.read_only_depends_on, doc) : false
}

/** The few `frappe.*` helpers that depends_on expressions in HRMS and ERPNext use. */
const frappeShim = {
	user: { has_role: (role: string) => hasRole(role) },
	get session() {
		return { user: session.user }
	},
	datetime: { get_today: () => new Date().toISOString().slice(0, 10) },
	boot: {},
}

const toNumber = (v: any) => {
	const n = parseFloat(v)
	return Number.isNaN(n) ? 0 : n
}

/** Globals the Desk form exposes to `eval:` expressions. */
const GLOBALS = {
	frappe: frappeShim,
	in_list: (list: any[], value: any) => Array.isArray(list) && list.includes(value),
	cint: (v: any) => Math.trunc(toNumber(v)),
	flt: toNumber,
	cstr: (v: any) => (v === null || v === undefined ? "" : String(v)),
	is_null: (v: any) => v === null || v === undefined || v === "",
}
