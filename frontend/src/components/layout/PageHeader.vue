<template>
	<header
		class="sticky top-0 z-30 flex h-12 shrink-0 items-center gap-2 border-b border-ch-line bg-ch-bg pl-3 pr-3 sm:pl-4"
	>
		<button
			class="flex size-8 shrink-0 items-center justify-center rounded-3 text-ch-ink-2 hover:bg-ch-subtle md:hidden"
			aria-label="Open navigation"
			@click="openSidebar?.()"
		>
			<span class="lucide-menu size-[18px]" />
		</button>
		<nav aria-label="Breadcrumb" class="flex min-w-0 flex-1 items-center gap-1 whitespace-nowrap text-[16px]">
			<template v-for="(crumb, index) in crumbs" :key="index">
				<span v-if="index > 0" class="hidden text-ch-ink-4 sm:inline">/</span>
				<RouterLink
					v-if="crumb.route && index < crumbs.length - 1"
					:to="crumb.route"
					class="hidden shrink-0 rounded-1 px-1 py-0.5 text-ch-ink-3 hover:bg-ch-subtle hover:text-ch-ink sm:inline"
				>
					{{ crumb.label }}
				</RouterLink>
				<span v-else aria-current="page" class="truncate px-1 py-0.5 font-medium text-ch-ink">
					{{ crumb.label }}
				</span>
			</template>
		</nav>
		<slot name="actions" />
	</header>
</template>

<script setup lang="ts">
import { inject, watchEffect } from "vue"

const props = defineProps<{ crumbs: { label: string; route?: string }[] }>()
const openSidebar = inject<() => void>("openSidebar")

watchEffect(() => {
	const current = props.crumbs[props.crumbs.length - 1]?.label
	document.title = current ? `${current} · CentHR` : "CentHR"
})
</script>
