<template>
	<Sidebar
		v-model:collapsed="collapsed"
		:collapsible="!mobile"
		width="232px"
		collapsed-width="56px"
		aria-label="Main navigation"
		class="h-full border-r border-ch-line !bg-ch-sb"
	>
		<SidebarHeader title="CentHR" :subtitle="session.fullName || session.user || ''" :menu-items="menu">
			<template #prefix>
				<span
					class="flex size-full items-center justify-center bg-ch-primary text-[15px] font-semibold text-ch-on-primary"
				>
					C
				</span>
			</template>
		</SidebarHeader>

		<div class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-1">
			<SidebarItem label="Dashboard" icon="lucide-layout-dashboard" route="/" :active="route.name === 'Dashboard'" @click="$emit('navigate')" />
			<SidebarSection
				v-for="group in visibleGroups"
				:key="group.label"
				v-model:collapsed="closedGroups[group.label]"
				:label="group.label"
				collapsible
				class="mt-2"
			>
				<SidebarItem
					v-for="item in group.items"
					:key="item.route"
					:label="item.label"
					:icon="item.icon"
					:route="item.route"
					:active="route.path === item.route || route.path.startsWith(item.route + '/')"
					@click="$emit('navigate')"
				/>
			</SidebarSection>
		</div>

		<div v-if="!mobile" class="px-2 pb-2">
			<SidebarCollapseToggle />
		</div>
	</Sidebar>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue"
import { useRoute } from "vue-router"
import {
	Sidebar,
	SidebarCollapseToggle,
	SidebarHeader,
	SidebarItem,
	SidebarSection,
	useColorScheme,
} from "frappe-ui"
import { can } from "@/data/permissions"
import { logout, session } from "@/data/session"
import { readStorage, writeStorage } from "@/utils/storage"

defineProps<{ mobile?: boolean }>()
defineEmits<{ navigate: [] }>()

const route = useRoute()
const { resolvedColorScheme, setColorScheme } = useColorScheme()

const groups = [
	{
		label: "Employee Master",
		items: [
			{ label: "Employees", icon: "lucide-users", route: "/employees", doctype: "Employee" },
			{ label: "Leave Allocation", icon: "lucide-calendar-plus", route: "/leave-allocations", doctype: "Leave Allocation" },
			{ label: "Shift", icon: "lucide-timer", route: "/shifts", doctype: "Shift Type" },
		],
	},
	{
		label: "Attendance & Leaves",
		items: [
			{ label: "Attendance", icon: "lucide-clock", route: "/attendance", doctype: "Attendance" },
			{ label: "Employee Checkin", icon: "lucide-fingerprint", route: "/checkins", doctype: "Employee Checkin" },
			{ label: "Leave Type", icon: "lucide-tags", route: "/leave-types", doctype: "Leave Type" },
			{ label: "Leave Application", icon: "lucide-file-text", route: "/leave-applications", doctype: "Leave Application" },
		],
	},
]

// Only modules the user can read; the server checks again on every request
const visibleGroups = computed(() =>
	groups
		.map((g) => ({ ...g, items: g.items.filter((item) => can(item.doctype).read) }))
		.filter((g) => g.items.length)
)

// Collapsed by default on tablets, as in the design; the user's choice is remembered
const tablet = window.innerWidth >= 768 && window.innerWidth < 1100
const collapsed = defineModel<boolean>("collapsed", { default: false })
collapsed.value = readStorage("centhr-sidebar", tablet ? "collapsed" : "expanded") === "collapsed"
watch(collapsed, (value) => writeStorage("centhr-sidebar", value ? "collapsed" : "expanded"))

const closedGroups = reactive<Record<string, boolean>>(JSON.parse(readStorage("centhr-nav-closed", "{}")))
watch(closedGroups, (value) => writeStorage("centhr-nav-closed", JSON.stringify(value)))

const menu = computed(() => [
	{
		group: "Account",
		hideLabel: true,
		options: [
			{
				label: resolvedColorScheme.value === "dark" ? "Light theme" : "Dark theme",
				icon: resolvedColorScheme.value === "dark" ? "lucide-sun" : "lucide-moon",
				onClick: () => setColorScheme(resolvedColorScheme.value === "dark" ? "light" : "dark"),
			},
			{ label: "Open Desk", icon: "lucide-app-window", onClick: () => (window.location.href = "/desk") },
		],
	},
	{
		group: "Session",
		hideLabel: true,
		options: [{ label: "Log out", icon: "lucide-log-out", onClick: logout }],
	},
])
</script>
