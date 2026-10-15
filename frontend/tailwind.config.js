import preset, { content } from "frappe-ui/tailwind"

const tone = (name) => ({
	bg: `var(--ch-${name}-bg)`,
	ink: `var(--ch-${name}-ink)`,
	dot: `var(--ch-${name}-dot)`,
})

/** @type {import('tailwindcss').Config} */
export default {
	presets: [preset],
	content: [...content, "./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
	// Status tones are picked at runtime (StatusBadge), so the scanner cannot see them
	safelist: ["prose", "prose-v3", { pattern: /^(bg|text)-ch-(green|amber|red|blue|gray)-(bg|ink|dot)$/ }],
	theme: {
		extend: {
			// CentHR design tokens; values live in src/style.css (light and dark)
			colors: {
				ch: {
					bg: "var(--ch-bg)",
					sb: "var(--ch-sb)",
					surface: "var(--ch-surface)",
					subtle: "var(--ch-subtle)",
					"subtle-2": "var(--ch-subtle-2)",
					hover: "var(--ch-hover)",
					"hover-sb": "var(--ch-hover-sb)",
					weekend: "var(--ch-weekend)",
					line: "var(--ch-line)",
					"line-2": "var(--ch-line-2)",
					ink: "var(--ch-ink)",
					"ink-2": "var(--ch-ink-2)",
					"ink-3": "var(--ch-ink-3)",
					"ink-4": "var(--ch-ink-4)",
					primary: "var(--ch-primary)",
					"primary-hover": "var(--ch-primary-hover)",
					"on-primary": "var(--ch-on-primary)",
					green: tone("green"),
					amber: tone("amber"),
					red: tone("red"),
					blue: tone("blue"),
					gray: tone("gray"),
				},
			},
			boxShadow: {
				"ch-xs": "var(--ch-shadow-xs)",
				"ch-menu": "var(--ch-shadow-menu)",
				"ch-card": "var(--ch-shadow)",
			},
		},
	},
}
