/** localStorage that never throws (private windows, blocked storage). */
export function readStorage(key: string, fallback: string): string {
	try {
		return localStorage.getItem(key) ?? fallback
	} catch {
		return fallback
	}
}

export function writeStorage(key: string, value: string) {
	try {
		localStorage.setItem(key, value)
	} catch {
		// Storage is optional; the UI just forgets the preference
	}
}
