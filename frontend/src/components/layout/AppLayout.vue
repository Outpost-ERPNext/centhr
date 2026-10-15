<template>
	<div class="flex h-screen w-full overflow-hidden bg-ch-bg text-ch-ink">
		<!-- Desktop and tablet -->
		<div class="hidden h-full shrink-0 md:block">
			<AppSidebar />
		</div>

		<!-- Mobile drawer -->
		<Transition name="fade">
			<div
				v-if="drawerOpen"
				class="fixed inset-0 z-40 bg-black/30 md:hidden"
				aria-hidden="true"
				@click="drawerOpen = false"
			/>
		</Transition>
		<Transition name="slide">
			<div v-if="drawerOpen" class="fixed inset-y-0 left-0 z-50 h-full w-[260px] shadow-ch-card md:hidden">
				<AppSidebar mobile @navigate="drawerOpen = false" />
			</div>
		</Transition>

		<div class="flex min-w-0 flex-1 flex-col">
			<RouterView v-slot="{ Component }">
				<component :is="Component" :key="$route.path" />
			</RouterView>
		</div>
	</div>
</template>

<script setup lang="ts">
import { provide, ref, watch } from "vue"
import { useRoute } from "vue-router"
import AppSidebar from "./AppSidebar.vue"

const drawerOpen = ref(false)
provide("openSidebar", () => (drawerOpen.value = true))

const route = useRoute()
watch(
	() => route.path,
	() => (drawerOpen.value = false)
)
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
.slide-enter-active,
.slide-leave-active {
	transition: transform 0.18s ease;
}
.slide-enter-from,
.slide-leave-to {
	transform: translateX(-100%);
}
</style>
