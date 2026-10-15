<template>
	<div class="flex min-h-screen flex-col items-center justify-center bg-ch-sb px-4 py-10 text-ch-ink">
		<button
			class="fixed right-4 top-4 flex size-8 items-center justify-center rounded-3 text-ch-ink-2 hover:bg-ch-subtle"
			:aria-label="dark ? 'Switch to light theme' : 'Switch to dark theme'"
			@click="setColorScheme(dark ? 'light' : 'dark')"
		>
			<span class="size-4" :class="dark ? 'lucide-sun' : 'lucide-moon'" />
		</button>

		<div class="w-full max-w-[380px] rounded-6 bg-ch-surface p-6 shadow-ch-card sm:p-8">
			<div class="mb-6 flex flex-col items-center gap-3 text-center">
				<span
					class="flex size-10 items-center justify-center rounded-4 bg-ch-primary text-[19px] font-semibold text-ch-on-primary"
				>
					C
				</span>
				<div>
					<h1 class="text-[20px] font-semibold tracking-[-0.01em]">
						{{ view === "login" ? "Sign in to CentHR" : "Reset your password" }}
					</h1>
					<p class="mt-1 text-[13px] text-ch-ink-3">
						{{
							view === "login"
								? "Use your work account to continue."
								: "We will email you a link to set a new password."
						}}
					</p>
				</div>
			</div>

			<div
				v-if="expired && view === 'login'"
				class="mb-4 flex gap-2 rounded-4 bg-ch-amber-bg px-3 py-2 text-[13px] text-ch-amber-ink"
				role="status"
			>
				<span class="lucide-clock mt-0.5 size-4 shrink-0" />
				<span>Your session expired. Sign in again to continue.</span>
			</div>
			<div
				v-if="error"
				class="mb-4 flex gap-2 rounded-4 bg-ch-red-bg px-3 py-2 text-[13px] text-ch-red-ink"
				role="alert"
			>
				<span class="lucide-circle-alert mt-0.5 size-4 shrink-0" />
				<span>{{ error }}</span>
			</div>
			<div
				v-if="resetSent"
				class="mb-4 flex gap-2 rounded-4 bg-ch-green-bg px-3 py-2 text-[13px] text-ch-green-ink"
				role="status"
			>
				<span class="lucide-check mt-0.5 size-4 shrink-0" />
				<span>If an account exists for {{ email }}, a reset link is on its way.</span>
			</div>

			<form v-if="view === 'login'" class="flex flex-col gap-4" @submit.prevent="signIn">
				<TextInput
					v-model="email"
					label="Email or username"
					autocomplete="username"
					size="md"
					required
					:disabled="loading"
				/>
				<Password
					v-model="password"
					label="Password"
					autocomplete="current-password"
					size="md"
					required
					:disabled="loading"
				/>
				<Button type="submit" variant="solid" size="md" :loading="loading" label="Sign in" class="w-full" />
				<button
					type="button"
					class="self-center text-[13px] text-ch-ink-3 hover:text-ch-ink"
					@click="switchView('forgot')"
				>
					Forgot password?
				</button>
			</form>

			<form v-else class="flex flex-col gap-4" @submit.prevent="sendReset">
				<TextInput v-model="email" label="Email" type="email" autocomplete="email" size="md" required />
				<Button type="submit" variant="solid" size="md" :loading="loading" label="Send reset link" class="w-full" />
				<button
					type="button"
					class="self-center text-[13px] text-ch-ink-3 hover:text-ch-ink"
					@click="switchView('login')"
				>
					Back to sign in
				</button>
			</form>
		</div>
		<p class="mt-6 text-[12px] text-ch-ink-4">CentHR</p>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { useRoute, useRouter } from "vue-router"
import { Button, call, Password, TextInput, useColorScheme } from "frappe-ui"
import { login } from "@/data/session"
import { errorMessage } from "@/data/api"
import { safeRedirect } from "@/router"

const route = useRoute()
const router = useRouter()
const { resolvedColorScheme, setColorScheme } = useColorScheme()
const dark = computed(() => resolvedColorScheme.value === "dark")

const view = ref<"login" | "forgot">("login")
const email = ref("")
const password = ref("")
const loading = ref(false)
const error = ref("")
const resetSent = ref(false)
const expired = computed(() => route.query.expired === "1")

document.title = "Sign in · CentHR"

function switchView(next: "login" | "forgot") {
	view.value = next
	error.value = ""
	resetSent.value = false
}

async function signIn() {
	if (!email.value || !password.value) return
	loading.value = true
	error.value = ""
	try {
		await login(email.value.trim(), password.value)
		await router.replace(safeRedirect(route.query.redirect))
	} catch (e) {
		error.value = errorMessage(e) || "Invalid login credentials"
	} finally {
		loading.value = false
	}
}

async function sendReset() {
	if (!email.value) return
	loading.value = true
	error.value = ""
	try {
		await call("frappe.core.doctype.user.user.reset_password", { user: email.value.trim() })
		resetSent.value = true
	} catch (e) {
		// The server answers the same way for unknown users, so this is a real failure (e.g. rate limit)
		error.value = errorMessage(e)
	} finally {
		loading.value = false
	}
}
</script>
