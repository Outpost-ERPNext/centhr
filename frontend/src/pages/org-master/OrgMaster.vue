<template>
	<PageHeader :crumbs="[{ label: 'Org Master' }]" />

	<div class="flex-1 overflow-y-auto">
		<div class="mx-auto flex max-w-[1240px] flex-col gap-5 p-4 sm:p-5">
			<div>
				<h1 class="text-[18px] font-semibold tracking-[-0.01em] text-ch-ink">Org Master</h1>
				<p class="mt-0.5 text-[13px] text-ch-ink-3">Set up the masters that describe your organisation.</p>
			</div>

			<div v-if="masters.length" class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
				<RouterLink
					v-for="m in masters"
					:key="m.route"
					:to="m.route"
					class="group flex flex-col gap-3 rounded-5 border border-ch-line bg-ch-surface p-4 hover:bg-ch-hover"
				>
					<div class="flex items-center gap-2">
						<span class="flex size-9 shrink-0 items-center justify-center rounded-3 bg-ch-subtle text-ch-ink-2">
							<span class="size-[18px]" :class="m.icon" />
						</span>
						<span class="lucide-arrow-right ml-auto size-4 text-ch-ink-3 opacity-0 transition-opacity group-hover:opacity-100" />
					</div>
					<div>
						<div class="text-[14px] font-medium text-ch-ink">{{ m.label }}</div>
						<div class="mt-0.5 text-[12.5px] text-ch-ink-3">{{ m.description }}</div>
					</div>
				</RouterLink>
			</div>
			<p v-else class="py-10 text-center text-[13px] text-ch-ink-3">You do not have access to any organisation masters.</p>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue"
import PageHeader from "@/components/layout/PageHeader.vue"
import { can } from "@/data/permissions"
import { ORG_MASTERS } from "@/data/orgMaster"

const masters = computed(() => ORG_MASTERS.filter((m) => can(m.doctype).read))
</script>
