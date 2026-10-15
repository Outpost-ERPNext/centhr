import { call } from "frappe-ui"

export interface SysDefaults {
	date_format: string
	time_format: string
	number_format: string
	currency: string | null
	time_zone: string
}

declare global {
	interface Window {
		csrf_token?: string
		user?: string
		app_name?: string
		site_name?: string
		sysdefaults?: SysDefaults
	}
}

/** The Vite dev server serves plain index.html, so it fetches the boot data that www/centhr.py injects in production. */
export async function loadDevBoot() {
	if (!import.meta.env.DEV) return
	try {
		const boot = await call<Record<string, any>>("centhr.www.centhr.get_context_for_dev")
		for (const [key, value] of Object.entries(boot)) {
			;(window as any)[key] = value
		}
	} catch (error) {
		console.error("Could not load boot data for development", error)
	}
}

export function sysdefaults(): SysDefaults {
	return (
		window.sysdefaults || {
			date_format: "dd-mm-yyyy",
			time_format: "HH:mm:ss",
			number_format: "#,###.##",
			currency: null,
			time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
		}
	)
}
