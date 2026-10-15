<template>
	<FrappeUIProvider>
		<RouterView />
	</FrappeUIProvider>
</template>

<script setup lang="ts">
import { FrappeUIProvider, useColorScheme } from "frappe-ui"

// Applies the saved theme (or the system one) before the first paint of the app
useColorScheme()
</script>
