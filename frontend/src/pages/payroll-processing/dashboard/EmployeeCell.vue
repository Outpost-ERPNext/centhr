<template>
	<div class="min-w-0">
		<div class="flex min-w-0">
			<!-- Not a button: on phones the table row around it is one already -->
			<span
				role="button"
				tabindex="0"
				class="truncate font-medium text-ch-ink hover:text-ch-primary hover:underline"
				:title="`Quick view of ${name}`"
				@click.stop="openEmployee(employee)"
				@keydown.enter.stop="openEmployee(employee)"
			>
				{{ name }}
			</span>
		</div>
		<div v-if="detail" class="truncate text-[12px] text-ch-ink-3">{{ detail }}</div>
	</div>
</template>

<script setup lang="ts">
import { inject } from "vue"
import { OPEN_EMPLOYEE } from "@/data/payrollDashboard"

/** An employee in a dashboard table. Their name opens their quick view; the rest of the row keeps its own click. */
defineProps<{ employee: string; name: string; detail?: string }>()
const openEmployee = inject(OPEN_EMPLOYEE)!
</script>
