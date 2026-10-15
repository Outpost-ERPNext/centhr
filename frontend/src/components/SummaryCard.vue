<template>
	<section class="rounded-5 border border-ch-line bg-ch-surface p-4">
		<h3 v-if="title" class="mb-3 text-[14px] font-medium text-ch-ink">{{ title }}</h3>
		<dl class="flex flex-col gap-2.5">
			<div v-for="item in items" :key="item.label" class="flex items-baseline justify-between gap-3 text-[13px]">
				<dt class="shrink-0 text-ch-ink-3">{{ item.label }}</dt>
				<dd class="min-w-0 truncate text-right text-ch-ink">
					<RouterLink
						v-if="item.route && item.value"
						:to="item.route"
						class="underline decoration-ch-line-2 underline-offset-2 hover:decoration-ch-ink"
					>
						{{ item.value }}
					</RouterLink>
					<template v-else>{{ item.value || "—" }}</template>
				</dd>
			</div>
		</dl>
		<slot />
	</section>
</template>

<script setup lang="ts">
defineProps<{ title?: string; items: { label: string; value?: string | number | null; route?: string | null }[] }>()
</script>
