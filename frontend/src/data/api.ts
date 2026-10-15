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

export function errorMessage(error: unknown): string {
	const err = error as FrappeResourceError
	const messages = (err?.messages || []).map(stripHtml).filter(Boolean)
	if (messages.length) return messages.join("\n")
	return err?.message ? stripHtml(err.message) : "Something went wrong"
}

function stripHtml(value: string) {
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
