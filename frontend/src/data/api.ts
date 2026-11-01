import { call, toast } from "frappe-ui"
import type { FrappeResourceError } from "frappe-ui"
import router from "@/router"
import { session } from "./session"

/**
 * POST to a whitelisted method. Errors are shown as a toast (unless `silent`)
 * and rethrown, so callers can keep their own state consistent.
 */
export async function api<T = any>(
	method: string,
	args: Record<string, any> = {},
	{ silent = false }: { silent?: boolean } = {}
): Promise<T> {
	try {
		return await call<T>(method, args)
	} catch (error) {
		const err = error as FrappeResourceError
		if (isSessionExpired(err)) {
			handleSessionExpired()
		} else if (isAuthError(err) && (redirecting || router.currentRoute.value.name === "Login")) {
			// Requests that were in flight when the session ended; the login page explains it
		} else if (!silent) {
			toast.error(errorMessage(err))
		}
		throw err
	}
}

/** POSTs to a whitelisted method that answers with a file, and saves that file. */
export async function downloadFile(method: string, args: Record<string, any>) {
	const body = new URLSearchParams()
	for (const [key, value] of Object.entries(args)) {
		if (value !== undefined && value !== null) body.append(key, typeof value === "string" ? value : JSON.stringify(value))
	}
	const response = await fetch(`/api/method/${method}`, {
		method: "POST",
		body,
		headers: { "X-Frappe-CSRF-Token": window.csrf_token || "" },
	})
	if (!response.ok) {
		toast.error(serverMessage(await response.json().catch(() => ({}))) || "Could not download the file")
		throw new Error("Download failed")
	}
	const name = response.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/)?.[1] || "download.xlsx"
	const url = URL.createObjectURL(await response.blob())
	const link = Object.assign(document.createElement("a"), { href: url, download: decodeURIComponent(name) })
	link.click()
	URL.revokeObjectURL(url)
}

/** The first message in a raw Frappe error response, for requests made without `call`. */
export function serverMessage(body: { _server_messages?: string; exception?: string }): string {
	try {
		const [first] = JSON.parse(body._server_messages || "[]")
		if (first) return stripHtml(JSON.parse(first).message)
	} catch {
		// Not the usual message format; fall back to the exception
	}
	return body.exception ? stripHtml(body.exception) : ""
}

export function errorMessage(error: unknown): string {
	const err = error as FrappeResourceError
	const messages = (err?.messages || []).map(stripHtml).filter(Boolean)
	if (messages.length) return messages.join("\n")
	return err?.message ? stripHtml(err.message) : "Something went wrong"
}

export function stripHtml(value: string) {
	const div = document.createElement("div")
	div.innerHTML = String(value)
	return (div.textContent || "").trim()
}

function cookieUser() {
	const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/)
	return match ? decodeURIComponent(match[1]) : null
}

function isSessionExpired(err: FrappeResourceError) {
	if (!session.user || session.user === "Guest") return false
	if (err?.exc_type === "SessionExpired" || err?.status === 401) return true
	// An expired sid makes the request run as Guest, which fails with a PermissionError
	return err?.status === 403 && (!cookieUser() || cookieUser() === "Guest")
}

const isAuthError = (err: FrappeResourceError) => err?.status === 401 || err?.status === 403

let redirecting = false
function handleSessionExpired() {
	if (redirecting) return
	redirecting = true
	session.user = null
	const current = router.currentRoute.value
	router
		.replace({ name: "Login", query: { expired: "1", redirect: current.fullPath } })
		.finally(() => setTimeout(() => (redirecting = false), 1000))
}
