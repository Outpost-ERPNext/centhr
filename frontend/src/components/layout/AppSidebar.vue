<template>
	<Sidebar
		v-model:collapsed="collapsed"
		:collapsible="!mobile"
		width="232px"
		collapsed-width="56px"
		aria-label="Main navigation"
		class="h-full border-r border-ch-line !bg-ch-sb"
	>
		<!-- Collapse control lives on the header row and shows on hover -->
		<div class="group/header relative">
			<SidebarHeader title="CentHR" :subtitle="session.fullName || session.user || ''" :menu-items="menu">
				<template #prefix>
					<span
						class="flex size-full items-center justify-center bg-ch-primary text-[15px] font-semibold text-ch-on-primary"
					>
						C
					</span>
				</template>
			</SidebarHeader>
			<template v-if="!mobile">
				<!-- Collapsed: the arrow takes the logo's place -->
				<button
					v-if="collapsed"
					class="absolute left-[10px] top-[10px] flex size-7 items-center justify-center rounded-[6px] bg-ch-subtle text-ch-ink-2 opacity-0 transition-opacity hover:text-ch-ink focus-visible:opacity-100 group-hover/header:opacity-100"
					aria-label="Expand sidebar"
					title="Expand sidebar"
					@click="collapsed = false"
				>
					<span class="lucide-chevron-right size-4" />
				</button>
				<button
					v-else
					class="absolute right-2 top-[10px] flex size-7 items-center justify-center rounded-3 bg-ch-sb text-ch-ink-3 opacity-0 transition-opacity hover:bg-ch-subtle hover:text-ch-ink focus-visible:opacity-100 group-hover/header:opacity-100"
					aria-label="Collapse sidebar"
					title="Collapse sidebar"
					@click="collapsed = true"
				>
					<span class="lucide-chevron-left size-4" />
				</button>
			</template>
		</div>

		<div class="flex flex-1 flex-col gap-0.5 overflow-y-auto px-2 py-1">
			<SidebarItem label="Dashboard" icon="lucide-layout-dashboard" route="/" :active="route.name === 'Dashboard'" @click="$emit('navigate')" />
			<SidebarItem label="Architecture" icon="lucide-brain-circuit" route="/architecture" @click="$emit('navigate')" />
			<SidebarItem label="Docs" icon="lucide-book-open" :href="DOCS_URL" target="_blank" rel="noopener" @click="$emit('navigate')" />
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
							<!-- Chevron right after the label, as on the group headings -->
							<span class="truncate text-sm leading-tighter">{{ item.label }}</span>
							<span
								class="lucide-chevron-right ml-1 size-4 shrink-0 text-ink-gray-5 transition-transform"
								:class="{ 'rotate-90': !closedGroups[item.label] }"
							/>
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
						:active="isActive(item.route) || item.activeOn?.some(isActive)"
						@click="$emit('navigate')"
					/>
				</template>
			</SidebarSection>
		</div>
	</Sidebar>
</template>

<script setup lang="ts">
import { computed, reactive, watch } from "vue"
import { useRoute } from "vue-router"
import {
	Sidebar,
	SidebarHeader,
	SidebarItem,
	SidebarSection,
	useColorScheme,
} from "frappe-ui"
import { can } from "@/data/permissions"
import { logout, session } from "@/data/session"
import { ORG_MASTERS } from "@/data/orgMaster"
import { readStorage, writeStorage } from "@/utils/storage"

// The CentHR space in Frappe Wiki, on this same site
const DOCS_URL = "/centhr-docs"

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
	/** Shown when the user can read at least one of these DocTypes. */
	doctypes?: string[]
	/** Pages opened from this item's page, which have no sidebar item of their own. */
	activeOn?: string[]
	/** A sub-menu inside the group, expanded and collapsed in place. */
	children?: NavLink[]
}

const groups: { label: string; items: NavItem[] }[] = [
	{
		label: "Employee Master",
		items: [
			{ label: "Employees", icon: "lucide-users", route: "/employees", doctype: "Employee" },
			{ label: "Leave Allocation", icon: "lucide-calendar-plus", route: "/leave-allocations", doctype: "Leave Allocation" },
			{
				label: "Shift",
				icon: "lucide-timer",
				route: "/shifts",
				doctype: "Shift Type",
				activeOn: ["/shift-assignments", "/shift-assignment-tool"],
			},
			{ label: "Holiday List", icon: "lucide-calendar-off", route: "/holiday-lists", doctype: "Holiday List" },
			{
				label: "Org Master",
				icon: "lucide-network",
				route: "/org-master",
				doctypes: ORG_MASTERS.map((m) => m.doctype),
				activeOn: ORG_MASTERS.map((m) => m.route),
			},
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
				label: "Payroll Processing",
				icon: "lucide-banknote",
				children: [
					{ label: "Payroll Dashboard", icon: "lucide-layout-dashboard", route: "/payroll-processing/payroll-entries", doctype: "Payroll Entry" },
					{ label: "Salary Slip", icon: "lucide-receipt", route: "/payroll-processing/salary-slips", doctype: "Salary Slip" },
				],
			},
		],
	},
	{
		label: "IOU",
		items: [
			{
				label: "IOU Dashboard",
				icon: "lucide-layout-dashboard",
				route: "/iou/dashboard",
				doctypes: ["IOU and Loans", "Employee Advance", "Expense Claim"],
			},
		],
	},
	{
		label: "Performance",
		items: [
			{ label: "KPI Dashboard", icon: "lucide-target", route: "/pms/kpi-results", doctype: "KPI Result" },
			{ label: "KPI Templates", icon: "lucide-clipboard-list", route: "/pms/kpi-templates", doctype: "KPI Template" },
			{
				label: "PMS Setup",
				icon: "lucide-sliders-horizontal",
				children: [
					{ label: "PMS Settings", icon: "lucide-settings", route: "/pms/settings", doctype: "PMS Settings" },
					{ label: "Question Bank", icon: "lucide-list-checks", route: "/pms/questions", doctype: "PMS Question" },
					{ label: "Question Traits", icon: "lucide-tags", route: "/pms/question-traits", doctype: "PMS Question Trait" },
					{ label: "KPI UOM", icon: "lucide-ruler", route: "/pms/kpi-uoms", doctype: "KPI UOM" },
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
				.filter((item) => {
					if (item.children) return item.children.length > 0
					if (item.doctypes) return item.doctypes.some((d) => can(d).read)
					return can(item.doctype!).read
				}),
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
