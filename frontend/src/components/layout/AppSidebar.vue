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
				<template v-for="item in group.items" :key="item.label">
					<template v-if="item.children">
						<SidebarItem
							:label="item.label"
							:icon="item.icon"
							:aria-expanded="!closedGroups[item.label]"
							@click="closedGroups[item.label] = !closedGroups[item.label]"
						>
							<template #suffix>
								<span
									class="lucide-chevron-right mr-1.5 size-4 text-ink-gray-5 transition-transform"
									:class="{ 'rotate-90': !closedGroups[item.label] }"
								/>
							</template>
						</SidebarItem>
						<!-- Icon-only sidebar has no room to indent or collapse, so it lists the children flat -->
						<div v-show="collapsed || !closedGroups[item.label]" class="flex flex-col gap-0.5" :class="{ 'pl-4': !collapsed }">
							<SidebarItem
								v-for="child in item.children"
								:key="child.route"
								:label="child.label"
								:icon="child.icon"
								:route="child.route"
								:active="isActive(child.route)"
								@click="$emit('navigate')"
							/>
						</div>
					</template>
					<SidebarItem
						v-else
						:label="item.label"
						:icon="item.icon"
						:route="item.route"
						:active="isActive(item.route)"
						@click="$emit('navigate')"
					/>
				</template>
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

interface NavLink {
	label: string
	icon: string
	route: string
	doctype: string
}
interface NavItem {
	label: string
	icon: string
	route?: string
	doctype?: string
	/** A sub-menu inside the group, expanded and collapsed in place. */
	children?: NavLink[]
}

const groups: { label: string; items: NavItem[] }[] = [
	{
		label: "Employee Master",
		items: [
			{ label: "Employees", icon: "lucide-users", route: "/employees", doctype: "Employee" },
			{ label: "Leave Allocation", icon: "lucide-calendar-plus", route: "/leave-allocations", doctype: "Leave Allocation" },
			{ label: "Shift", icon: "lucide-timer", route: "/shifts", doctype: "Shift Type" },
			{ label: "Shift Assignment", icon: "lucide-calendar-clock", route: "/shift-assignments", doctype: "Shift Assignment" },
			{ label: "Shift Assignment Tool", icon: "lucide-users-round", route: "/shift-assignment-tool", doctype: "Shift Assignment Tool" },
			{ label: "Holiday List", icon: "lucide-calendar-off", route: "/holiday-lists", doctype: "Holiday List" },
		],
	},
	{
		label: "Organization",
		items: [
			{ label: "Department", icon: "lucide-building-2", route: "/departments", doctype: "Department" },
			{ label: "Grade", icon: "lucide-award", route: "/grades", doctype: "Employee Grade" },
			{ label: "Designation", icon: "lucide-briefcase", route: "/designations", doctype: "Designation" },
		],
	},
	{
		label: "Attendance & Leaves",
		items: [
			{ label: "Attendance", icon: "lucide-clock", route: "/attendance", doctype: "Attendance" },
			{
				label: "Attendance Request",
				icon: "lucide-calendar-plus",
				route: "/attendance-requests",
				doctype: "Attendance Request",
			},
			{ label: "Employee Checkin", icon: "lucide-fingerprint", route: "/checkins", doctype: "Employee Checkin" },
			{ label: "Leave Type", icon: "lucide-tags", route: "/leave-types", doctype: "Leave Type" },
			{ label: "Leave Application", icon: "lucide-file-text", route: "/leave-applications", doctype: "Leave Application" },
		],
	},
	{
		label: "Payroll",
		items: [
			{
				label: "Salary Structure Assignment",
				icon: "lucide-wallet",
				route: "/salary-structure-assignments",
				doctype: "Salary Structure Assignment",
			},
			{
				label: "Payroll Processing",
				icon: "lucide-banknote",
				children: [
					{ label: "Payroll Entry", icon: "lucide-calculator", route: "/payroll-processing/payroll-entries", doctype: "Payroll Entry" },
					{ label: "Salary Slip", icon: "lucide-receipt", route: "/payroll-processing/salary-slips", doctype: "Salary Slip" },
				],
			},
		],
	},
]

// Only modules the user can read; the server checks again on every request
const visibleGroups = computed(() =>
	groups
		.map((g) => ({
			...g,
			items: g.items
				.map((item) => (item.children ? { ...item, children: item.children.filter((c) => can(c.doctype).read) } : item))
				.filter((item) => (item.children ? item.children.length : can(item.doctype!).read)),
		}))
		.filter((g) => g.items.length)
)

function isActive(path: string | undefined) {
	return !!path && (route.path === path || route.path.startsWith(path + "/"))
}

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
