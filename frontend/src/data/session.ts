import { reactive } from "vue"
import { call } from "frappe-ui"

interface Session {
	user: string | null
	fullName: string
	image: string | null
	roles: string[]
	loaded: boolean
}

function bootUser(): string | null {
	const fromBoot = window.user && window.user !== "Guest" ? window.user : null
	if (fromBoot) return fromBoot
	const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/)
	const fromCookie = match ? decodeURIComponent(match[1]) : null
	return fromCookie && fromCookie !== "Guest" ? fromCookie : null
}

export const session = reactive<Session>({
	user: bootUser(),
	fullName: "",
	image: null,
	roles: [],
	loaded: false,
})

export const isLoggedIn = () => !!session.user && session.user !== "Guest"

/** Loads the user's name, image and roles once per page load. */
export async function loadUser() {
	if (!isLoggedIn() || session.loaded) return
	try {
		const info = await call<{ name: string; full_name: string; user_image: string | null; roles: string[] }>(
			"hrms.api.get_current_user_info"
		)
		session.fullName = info.full_name || info.name
		session.image = info.user_image
		session.roles = info.roles || []
		session.loaded = true
	} catch {
		// A stale cookie: the server no longer knows this session
		session.user = null
	}
}

export async function login(usr: string, pwd: string) {
	const res = await call<{ message: string; full_name?: string; home_page?: string }>("login", { usr, pwd })
	session.user = bootUserAfterLogin() || usr
	session.loaded = false
	// The CSRF token is tied to the session, so get a fresh page token
	await refreshCsrfToken()
	await loadUser()
	return res
}

export async function logout() {
	try {
		await call("logout")
	} finally {
		session.user = null
		session.loaded = false
		session.roles = []
		// A full reload drops cached data and gets a fresh Guest CSRF token
		window.location.href = "/centhr/login"
	}
}

export function hasRole(...roles: string[]) {
	if (session.user === "Administrator") return true
	return roles.some((role) => session.roles.includes(role))
}

export const isHR = () => hasRole("HR Manager", "HR User", "System Manager")

function bootUserAfterLogin() {
	const match = document.cookie.match(/(?:^|;\s*)user_id=([^;]*)/)
	const user = match ? decodeURIComponent(match[1]) : null
	return user && user !== "Guest" ? user : null
}

async function refreshCsrfToken() {
	// The page was rendered for Guest, so its CSRF token belongs to the old session.
	// Reloading the page HTML is the only supported way to get a token for the new session.
	try {
		const response = await fetch(window.location.pathname, { credentials: "include" })
		const html = await response.text()
		const match = html.match(/window\["csrf_token"\]\s*=\s*"([^"]+)"/)
		if (match) window.csrf_token = match[1]
	} catch {
		// Dev server: the token comes from get_context_for_dev instead
	}
	if (import.meta.env.DEV) {
		const boot = await call<Record<string, any>>("centhr.www.centhr.get_context_for_dev")
		window.csrf_token = boot.csrf_token
	}
}
