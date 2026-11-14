<template>
	<div class="arch fixed inset-0 flex flex-col overflow-hidden text-[#d6e4fa] md:flex-row">
		<div class="relative min-h-0 min-w-0 flex-1">
			<canvas ref="canvas" class="absolute inset-0 h-full w-full touch-none select-none" style="cursor: grab" />

			<header class="pointer-events-none absolute left-4 right-4 top-4 flex flex-col gap-3 md:left-6 md:top-5">
				<div class="pointer-events-auto flex items-center gap-3">
					<RouterLink to="/" class="grid h-7 w-7 place-items-center rounded-full border border-white/10 text-[#9fb3d4] transition hover:border-white/25 hover:text-white" title="Back to CentHR">
						<span class="lucide-arrow-left h-3.5 w-3.5" />
					</RouterLink>
					<div>
						<h1 class="text-[13px] font-semibold tracking-wide text-white">CentHR Architecture</h1>
						<p class="text-[11px] text-[#7f93b5]">
							{{ status }}
						</p>
					</div>
				</div>

				<div v-if="sites.length" class="pointer-events-auto flex flex-wrap gap-1.5">
					<button
						v-for="site in sites"
						:key="site.company"
						class="chip"
						:class="{ off: net.hidden.has(site.company) }"
						:aria-pressed="!net.hidden.has(site.company)"
						:title="net.hidden.has(site.company) ? 'Show network' : 'Hide network'"
						@click="toggleCompany(site.company)"
					>
						<span class="dot" />
						{{ site.company }}
					</button>
				</div>
			</header>

			<div class="absolute right-4 top-4 flex rounded-full border border-white/10 bg-[#0a1226]/70 p-0.5 backdrop-blur md:top-5" role="tablist" aria-label="View">
				<button
					v-for="option in VIEWS"
					:key="option.value"
					role="tab"
					:aria-selected="layout === option.value"
					class="rounded-full px-3 py-1 text-[11px] font-medium transition"
					:class="layout === option.value ? 'bg-white/10 text-white' : 'text-[#7f93b5] hover:text-white'"
					:title="option.hint"
					@click="setLayout(option.value)"
				>
					{{ option.label }}
				</button>
			</div>

			<div v-if="state === 'empty'" class="absolute inset-0 grid place-items-center px-6 text-center">
				<div class="max-w-xs">
					<p class="text-[13px] font-medium text-white">No sites connected</p>
					<p class="mt-1 text-[12px] leading-relaxed text-[#7f93b5]">Add rows in CentHr Settings → Authorization to connect company HRMS sites to CentHR.</p>
				</div>
			</div>

			<div class="absolute bottom-4 left-4 flex items-end gap-4 md:bottom-5 md:left-6">
				<div class="flex flex-col overflow-hidden rounded-lg border border-white/10 bg-[#0a1226]/70 backdrop-blur">
					<button class="ctl" title="Zoom in" @click="net.zoomBy(1.25)"><span class="lucide-plus h-3.5 w-3.5" /></button>
					<button class="ctl border-y border-white/10" title="Zoom out" @click="net.zoomBy(0.8)"><span class="lucide-minus h-3.5 w-3.5" /></button>
					<button class="ctl" title="Reset view" @click="net.reset()"><span class="lucide-scan h-3.5 w-3.5" /></button>
				</div>
				<ul class="hidden flex-col gap-1.5 text-[11px] text-[#9fb3d4] sm:flex">
					<li v-for="(style, kind) in EDGE_STYLES" :key="kind" class="flex items-center gap-2" :title="style.hint">
						<span class="w-5 border-t" :class="{ 'border-dashed': kind === 'sync' }" :style="{ borderColor: style.color }" />
						{{ style.label }}
					</li>
					<li v-if="layout === 'layered'" class="mt-1 text-[#61759a]">Read left to right: input → hidden → output</li>
				</ul>
			</div>

			<div v-if="net.hover.value" class="tip" :style="tipStyle">
				<template v-if="net.hover.value.edge">
					<div class="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider" :style="{ color: EDGE_STYLES[net.hover.value.edge.kind].color }">
						<span class="h-1.5 w-1.5 rounded-full" :style="{ background: EDGE_STYLES[net.hover.value.edge.kind].color }" />
						{{ EDGE_STYLES[net.hover.value.edge.kind].label }}
					</div>
					<div class="mt-1 font-medium text-white">{{ net.hover.value.edge.title }}</div>
					<div class="mt-0.5 text-[#9fb3d4]">{{ net.hover.value.edge.detail }}</div>
					<div class="mt-1 text-[#61759a]">{{ EDGE_STYLES[net.hover.value.edge.kind].hint }}</div>
				</template>
				<template v-else-if="net.hover.value.node">
					<div class="font-medium text-white">{{ net.hover.value.node.label }}</div>
					<div class="text-[#7f93b5]">{{ nodeHint(net.hover.value.node) }}</div>
				</template>
			</div>
		</div>

		<aside class="panel max-h-[42%] shrink-0 overflow-y-auto border-t border-white/[0.07] px-5 py-5 md:max-h-none md:w-[320px] md:border-l md:border-t-0">
			<template v-if="selectedNode?.kind === 'company' && selectedNode.site">
				<p class="eyebrow">Company network</p>
				<h2 class="title">{{ selectedNode.label }}</h2>
				<p v-if="selectedNode.site.host" class="mt-0.5 font-mono text-[11px] text-[#7f93b5]">{{ selectedNode.site.host }}</p>
				<p class="body mt-3">
					Records whose company is {{ selectedNode.label }} are pushed to this site. Shift Type and Salary Component have no company, so they go to every connected site.
				</p>
				<button v-if="layout === 'radial'" class="mt-3 text-[11px] font-medium text-[#38d9f5] hover:text-white" @click="net.toggleExpanded(selectedNode.company!)">
					{{ net.expanded.has(selectedNode.company!) ? "Collapse modules" : "Expand modules" }}
				</button>
				<section class="sec">
					<p class="eyebrow">HRMS modules</p>
					<button v-for="module in MODULES" :key="module.key" class="row" @click="openModule(selectedNode.company!, module.key)">
						<span>{{ module.label }}</span>
						<span class="text-[10px] text-[#61759a]">{{ module.pushes.length ? "push" : "" }}{{ module.pushes.length && module.pull.length ? " · " : "" }}{{ module.pull.length ? "pull" : "" }}</span>
					</button>
				</section>
			</template>

			<template v-else-if="selectedNode?.kind === 'module' && selectedNode.module">
				<p class="eyebrow">{{ selectedNode.company || "CentHR" }} · module</p>
				<h2 class="title">{{ selectedNode.module.label }}</h2>
				<p class="body mt-2">{{ selectedNode.module.summary }}</p>
				<div class="mt-3 flex flex-wrap gap-1">
					<span v-for="doctype in selectedNode.module.doctypes" :key="doctype" class="tag">{{ doctype }}</span>
				</div>
				<section v-for="block in moduleBlocks(selectedNode.module)" :key="block.label" class="sec">
					<p class="eyebrow flex items-center gap-1.5">
						<span class="h-1.5 w-1.5 rounded-full" :style="{ background: block.color }" />
						{{ block.label }}
					</p>
					<ul class="list">
						<li v-for="item in block.items" :key="item">{{ item }}</li>
					</ul>
				</section>
				<section class="sec">
					<p class="eyebrow">Source</p>
					<p v-for="file in selectedNode.module.files" :key="file" class="font-mono text-[10.5px] leading-5 text-[#7f93b5]">centhr/{{ file }}</p>
				</section>
			</template>

			<template v-else-if="selectedNode?.kind === 'process' && selectedNode.process">
				<p class="eyebrow">Inside CentHR</p>
				<h2 class="title">{{ selectedNode.process.label }}</h2>
				<p class="body mt-2">{{ selectedNode.process.summary }}</p>
				<ul class="list sec">
					<li v-for="point in selectedNode.process.points" :key="point">{{ point }}</li>
				</ul>
				<section class="sec">
					<p class="eyebrow">Source</p>
					<p v-for="file in selectedNode.process.files" :key="file" class="font-mono text-[10.5px] leading-5 text-[#7f93b5]">{{ file }}</p>
				</section>
			</template>

			<template v-else>
				<p class="eyebrow">Central brain</p>
				<h2 class="title">CentHR</h2>
				<p class="body mt-2">{{ CORE.summary }}</p>
				<dl class="mt-4 grid grid-cols-3 gap-2 text-center">
					<div v-for="stat in coreStats" :key="stat.label" class="rounded-md border border-white/[0.06] py-2">
						<dt class="text-[15px] font-semibold text-white">{{ stat.value }}</dt>
						<dd class="text-[10px] text-[#7f93b5]">{{ stat.label }}</dd>
					</div>
				</dl>
				<section class="sec">
					<p class="eyebrow">Core responsibilities</p>
					<div v-for="item in CORE.responsibilities" :key="item.title" class="mt-2.5">
						<p class="text-[12px] font-medium text-white">{{ item.title }}</p>
						<p class="body">{{ item.text }}</p>
					</div>
				</section>
			</template>
		</aside>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { readStorage, writeStorage } from "@/utils/storage"
import { api } from "@/data/api"
import { buildGraph, buildLayeredGraph, CORE, EDGE_STYLES, MIGRATION_SECTIONS, MODULES, PROCESSES, type GraphNode, type ModuleDef, type Site } from "./topology"
import { useNeuralCanvas, type Layout } from "./useNeuralCanvas"

const VIEWS: { value: Layout; label: string; hint: string }[] = [
	{ value: "radial", label: "Network", hint: "CentHR as the brain, with company networks around it" },
	{ value: "layered", label: "Layered", hint: "Input → hidden → output, read left to right" },
]
const LAYOUT_KEY = "centhr:architecture-layout"

const canvas = ref<HTMLCanvasElement | null>(null)
const net = useNeuralCanvas(canvas)
const sites = ref<Site[]>([])
const nodes = ref<GraphNode[]>([])
const state = ref<"loading" | "ready" | "empty" | "error">("loading")
const layout = ref<Layout>(readStorage(LAYOUT_KEY, "radial") === "layered" ? "layered" : "radial")

const nodeById = computed(() => new Map(nodes.value.map((n) => [n.id, n])))
const selectedNode = computed(() => nodeById.value.get(net.selected.value || "core"))

const status = computed(() => {
	if (state.value === "loading") return "Connecting…"
	if (state.value === "error") return "Could not load connected sites"
	const count = sites.value.length
	return `${count} connected ${count === 1 ? "site" : "sites"} · ${MODULES.length} modules each`
})

const coreStats = computed(() => [
	{ value: sites.value.length, label: "Sites" },
	{ value: new Set(MODULES.flatMap((m) => m.pushes)).size, label: "Pushed doctypes" },
	{ value: MIGRATION_SECTIONS.length, label: "Migration sections" },
])

const tipStyle = computed(() => {
	const h = net.hover.value
	if (!h) return {}
	const flip = canvas.value && h.x > canvas.value.clientWidth - 260
	return { left: `${flip ? h.x - 254 : h.x + 14}px`, top: `${h.y + 14}px` }
})

onMounted(async () => {
	try {
		sites.value = (await api<Site[]>("centhr.api.architecture.get_connected_sites")) || []
	} catch {
		state.value = "error"
	}
	render()
	if (state.value !== "error") state.value = sites.value.length ? "ready" : "empty"
})

function render() {
	const graph = layout.value === "layered" ? buildLayeredGraph(sites.value) : buildGraph(sites.value)
	nodes.value = graph.nodes
	net.load(graph, layout.value)
	net.selected.value = layout.value === "layered" ? "process:queue" : "core"
}

function setLayout(value: Layout) {
	if (layout.value === value) return
	layout.value = value
	writeStorage(LAYOUT_KEY, value)
	render()
}

function toggleCompany(company: string) {
	net.hidden.has(company) ? net.hidden.delete(company) : net.hidden.add(company)
	if (net.hidden.has(company) && selectedNode.value?.company === company) net.selected.value = layout.value === "layered" ? "process:queue" : "core"
}

function openModule(company: string, key: string) {
	if (layout.value === "layered") {
		net.selected.value = `module:${key}`
		return
	}
	net.toggleExpanded(company, true)
	net.selected.value = `company:${company}/${key}`
}

function nodeHint(node: GraphNode) {
	if (node.kind === "core") return "Central brain · click for responsibilities"
	if (node.kind === "company" && layout.value === "layered") return "Company site · click for details"
	if (node.kind === "company") return net.expanded.has(node.company!) ? "Click to collapse modules" : "Click to expand HRMS modules"
	if (node.kind === "process") return PROCESSES.find((p) => p.key === node.process?.key)?.summary
	return "Click to see the data exchanged"
}

function moduleBlocks(module: ModuleDef) {
	return [
		{ label: "Pushed to the site", color: EDGE_STYLES.request.color, items: module.push },
		{ label: "Migrated into CentHR", color: EDGE_STYLES.sync.color, items: module.pull },
		{ label: "Inside CentHR", color: EDGE_STYLES.internal.color, items: module.local },
		{ label: "Not synced", color: "#61759a", items: module.notSynced },
	].filter((block) => block.items.length)
}
</script>

<style scoped>
.arch {
	background: radial-gradient(ellipse at 40% 45%, #0b1630 0%, #070c1b 45%, #04060d 100%);
	color-scheme: dark;
}
.panel {
	background: rgba(6, 10, 22, 0.72);
	backdrop-filter: blur(12px);
}
.eyebrow {
	font-size: 10px;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: #61759a;
}
.title {
	margin-top: 4px;
	font-size: 17px;
	font-weight: 600;
	color: #fff;
}
.body {
	font-size: 12px;
	line-height: 1.55;
	color: #9fb3d4;
}
.sec {
	margin-top: 20px;
	padding-top: 16px;
	border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.list {
	margin-top: 8px;
	display: flex;
	flex-direction: column;
	gap: 6px;
	font-size: 12px;
	line-height: 1.5;
	color: #b6c6e0;
}
.list li {
	position: relative;
	padding-left: 12px;
}
.list li::before {
	content: "";
	position: absolute;
	left: 0;
	top: 0.6em;
	width: 4px;
	height: 1px;
	background: #61759a;
}
.tag {
	border: 1px solid rgba(96, 165, 250, 0.22);
	border-radius: 999px;
	padding: 1px 8px;
	font-size: 10.5px;
	color: #9cc4f5;
}
.row {
	margin-top: 4px;
	display: flex;
	width: 100%;
	align-items: center;
	justify-content: space-between;
	border-radius: 6px;
	padding: 6px 8px;
	font-size: 12px;
	color: #d6e4fa;
	transition: background 0.15s;
}
.row:hover {
	background: rgba(255, 255, 255, 0.04);
}
.chip {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	border: 1px solid rgba(45, 212, 191, 0.25);
	border-radius: 999px;
	background: rgba(8, 16, 34, 0.6);
	padding: 3px 10px;
	font-size: 11px;
	color: #d6e4fa;
	backdrop-filter: blur(6px);
	transition: all 0.2s;
}
.chip .dot {
	width: 6px;
	height: 6px;
	border-radius: 999px;
	background: #2dd4bf;
	box-shadow: 0 0 6px rgba(45, 212, 191, 0.6);
}
.chip.off {
	border-color: rgba(255, 255, 255, 0.08);
	color: #61759a;
}
.chip.off .dot {
	background: transparent;
	box-shadow: inset 0 0 0 1px #61759a;
}
.ctl {
	display: grid;
	height: 30px;
	width: 30px;
	place-items: center;
	color: #9fb3d4;
	transition: color 0.15s, background 0.15s;
}
.ctl:hover {
	color: #fff;
	background: rgba(255, 255, 255, 0.05);
}
.tip {
	pointer-events: none;
	position: absolute;
	z-index: 10;
	max-width: 240px;
	border: 1px solid rgba(255, 255, 255, 0.08);
	border-radius: 8px;
	background: rgba(6, 11, 24, 0.92);
	padding: 8px 10px;
	font-size: 11px;
	line-height: 1.45;
	backdrop-filter: blur(8px);
}
</style>
