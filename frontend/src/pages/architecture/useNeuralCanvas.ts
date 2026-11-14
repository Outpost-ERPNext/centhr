import { onBeforeUnmount, onMounted, reactive, ref, shallowRef, type Ref } from "vue"
import { EDGE_STYLES, type GraphEdge, type GraphNode, type NodeKind } from "./topology"

/** Renders the CentHR graph as an animated neural network on a 2D canvas. */

const COMPANY_RING = 300
const PROCESS_RING = 92
const MODULE_ORBIT = 112
/** Arc the modules of a company fan out over, wide enough for eight without overlap */
const MODULE_ARC = Math.PI * 1.4
const LAYER_GAP = 300
const ROW_GAP = 72
const MIN_ZOOM = 0.4
const MAX_ZOOM = 3

const NODE_STYLE: Record<NodeKind, { radius: number; color: string }> = {
	core: { radius: 26, color: "#7dd3fc" },
	process: { radius: 6.5, color: "#8b93c9" },
	company: { radius: 14, color: "#2dd4bf" },
	module: { radius: 7, color: "#60a5fa" },
}

const PARTICLES: Record<string, { count: number; speed: number }> = {
	request: { count: 3, speed: 0.2 },
	response: { count: 2, speed: 0.16 },
	sync: { count: 1, speed: 0.09 },
	internal: { count: 1, speed: 0.12 },
}

export type Layout = "radial" | "layered"

interface Vec {
	x: number
	y: number
}

interface SimNode extends GraphNode {
	pos: Vec
	dormant: Vec
	radius: number
	color: string
	phase: number
	alpha: number
	open: number
	flash: number
}

interface SimEdge extends GraphEdge {
	a: SimNode
	b: SimNode
	particles: { offset: number; last: number }[]
	speed: number
}

interface Ghost {
	x: number
	y: number
	depth: number
	r: number
	phase: number
}

export interface HoverInfo {
	x: number
	y: number
	edge?: GraphEdge
	node?: GraphNode
}

export function useNeuralCanvas(canvas: Ref<HTMLCanvasElement | null>) {
	const selected = ref<string | null>("core")
	const expanded = reactive(new Set<string>())
	const hidden = reactive(new Set<string>())
	const hover = shallowRef<HoverInfo | null>(null)
	const zoomLevel = ref(1)

	const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches
	const view = { zoom: 1, pan: { x: 0, y: 0 }, target: null as null | { zoom: number; pan: Vec } }
	const size = { w: 0, h: 0, dpr: 1 }
	let nodes: SimNode[] = []
	let edges: SimEdge[] = []
	let byId = new Map<string, SimNode>()
	let columns: { title: string; caption: string; x: number; y: number }[] = []
	const ghosts = makeGhosts()
	const ghostLinks = linkGhosts(ghosts)

	let ctx: CanvasRenderingContext2D | null = null
	let frame = 0
	let last = performance.now()
	let time = 0
	let observer: ResizeObserver | null = null
	const pointer = { down: false, moved: false, start: { x: 0, y: 0 }, pan: { x: 0, y: 0 } }

	function load(graph: { nodes: GraphNode[]; edges: GraphEdge[]; columns?: { title: string; caption: string }[] }, layout: Layout = "radial") {
		const companies = graph.nodes.filter((n) => n.kind === "company")
		const processes = graph.nodes.filter((n) => n.kind === "process")
		const angleOf = new Map<string, number>()
		companies.forEach((n, i) => angleOf.set(n.company!, -Math.PI / 2 + (i * Math.PI * 2) / Math.max(companies.length, 1)))

		nodes = graph.nodes.map((n) => {
			const style = NODE_STYLE[n.kind]
			const node: SimNode = { ...n, pos: { x: 0, y: 0 }, dormant: { x: 0, y: 0 }, radius: n.size ?? style.radius, color: style.color, phase: hash(n.id) * Math.PI * 2, alpha: 0, open: 0, flash: 0 }
			if (layout === "layered") {
				const column = graph.nodes.filter((m) => m.layer === n.layer)
				node.pos = { x: (n.layer! - 1.5) * LAYER_GAP, y: (column.indexOf(n) - (column.length - 1) / 2) * ROW_GAP }
				node.dormant = node.pos
			} else if (n.kind === "process") {
				const i = processes.indexOf(n)
				const angle = Math.PI / 4 + (i * Math.PI * 2) / processes.length
				node.pos = polar(angle, PROCESS_RING)
			} else if (n.kind === "company") {
				node.pos = polar(angleOf.get(n.company!)!, COMPANY_RING)
			}
			return node
		})
		byId = new Map(nodes.map((n) => [n.id, n]))
		const top = Math.min(0, ...nodes.map((n) => n.pos.y)) - 78
		columns = layout === "layered" ? (graph.columns || []).map((c, i) => ({ ...c, x: (i - 1.5) * LAYER_GAP, y: top })) : []

		for (const company of layout === "radial" ? nodes.filter((n) => n.kind === "company") : []) {
			const modules = nodes.filter((n) => n.kind === "module" && n.company === company.company)
			const base = angleOf.get(company.company!)!
			const spread = MODULE_ARC / Math.max(modules.length - 1, 1)
			modules.forEach((m, i) => {
				const jitter = (hash(m.id + "j") - 0.5) * 0.22
				const angle = base - MODULE_ARC / 2 + i * spread + jitter
				const dist = MODULE_ORBIT * (0.86 + hash(m.id + "d") * 0.28)
				m.pos = add(company.pos, polar(angle, dist))
				m.dormant = add(company.pos, polar(angle, 30))
			})
		}

		edges = graph.edges
			.filter((e) => byId.has(e.from) && byId.has(e.to))
			.map((e) => {
				const p = PARTICLES[e.kind]
				const count = reducedMotion ? 1 : p.count
				return {
					...e,
					a: byId.get(e.from)!,
					b: byId.get(e.to)!,
					speed: p.speed * (0.85 + hash(e.id) * 0.3),
					particles: Array.from({ length: count }, (_, i) => ({ offset: i / count + hash(e.id + i) * 0.2, last: 0 })),
				}
			})
		reset(true)
	}

	// ---- interaction -------------------------------------------------------

	function toWorld(x: number, y: number): Vec {
		return { x: (x - size.w / 2 - view.pan.x) / view.zoom, y: (y - size.h / 2 - view.pan.y) / view.zoom }
	}

	function nodeAt(p: Vec) {
		const pad = 6 / view.zoom
		let found: SimNode | null = null
		for (const n of nodes) {
			if (visibility(n) < 0.35) continue
			const r = currentRadius(n) + pad
			if (dist(p, currentPos(n)) <= r) found = n
		}
		return found
	}

	function edgeAt(p: Vec) {
		const limit = 5 / view.zoom
		let best: SimEdge | null = null
		let bestDist = limit
		for (const e of edges) {
			if (edgeAlpha(e) < 0.3) continue
			const c = control(e)
			const a = currentPos(e.a)
			const b = currentPos(e.b)
			for (let i = 0; i <= 24; i++) {
				const d = dist(p, bezier(a, c, b, i / 24))
				if (d < bestDist) {
					bestDist = d
					best = e
				}
			}
		}
		return best
	}

	function onPointerDown(ev: PointerEvent) {
		pointer.down = true
		pointer.moved = false
		pointer.start = { x: ev.clientX, y: ev.clientY }
		pointer.pan = { ...view.pan }
		view.target = null
		canvas.value?.setPointerCapture(ev.pointerId)
	}

	function onPointerMove(ev: PointerEvent) {
		const local = localPoint(ev)
		if (pointer.down) {
			const dx = ev.clientX - pointer.start.x
			const dy = ev.clientY - pointer.start.y
			if (Math.hypot(dx, dy) > 4) pointer.moved = true
			if (pointer.moved) {
				view.pan = { x: pointer.pan.x + dx, y: pointer.pan.y + dy }
				hover.value = null
				return
			}
		}
		const world = toWorld(local.x, local.y)
		const node = nodeAt(world)
		const edge = node ? null : edgeAt(world)
		hover.value = node ? { x: local.x, y: local.y, node } : edge ? { x: local.x, y: local.y, edge } : null
		if (canvas.value) canvas.value.style.cursor = node ? "pointer" : edge ? "help" : pointer.down ? "grabbing" : "grab"
	}

	function onPointerUp(ev: PointerEvent) {
		if (pointer.down && !pointer.moved) {
			const local = localPoint(ev)
			click(nodeAt(toWorld(local.x, local.y)))
		}
		pointer.down = false
	}

	function onPointerLeave() {
		hover.value = null
	}

	function click(node: SimNode | null) {
		if (!node) return
		selected.value = node.id
		if (node.kind === "company") toggleExpanded(node.company!)
	}

	function toggleExpanded(company: string, open?: boolean) {
		const next = open ?? !expanded.has(company)
		next ? expanded.add(company) : expanded.delete(company)
	}

	function select(id: string) {
		const node = byId.get(id)
		if (node) click(node)
	}

	function onWheel(ev: WheelEvent) {
		ev.preventDefault()
		const local = localPoint(ev)
		zoomAt(Math.exp(-ev.deltaY * 0.0015), local)
	}

	function zoomAt(factor: number, at: Vec = { x: size.w / 2, y: size.h / 2 }) {
		view.target = null
		const before = toWorld(at.x, at.y)
		view.zoom = clamp(view.zoom * factor, MIN_ZOOM, MAX_ZOOM)
		view.pan = { x: at.x - size.w / 2 - before.x * view.zoom, y: at.y - size.h / 2 - before.y * view.zoom }
		zoomLevel.value = view.zoom
	}

	function zoomBy(factor: number) {
		zoomAt(factor)
	}

	function reset(instant = false) {
		const box = { minX: Infinity, minY: Infinity, maxX: -Infinity, maxY: -Infinity }
		const include = (p: Vec, pad: number) => {
			box.minX = Math.min(box.minX, p.x - pad)
			box.maxX = Math.max(box.maxX, p.x + pad)
			box.minY = Math.min(box.minY, p.y - pad)
			box.maxY = Math.max(box.maxY, p.y + pad + 22)
		}
		for (const n of nodes) {
			if (n.company && hidden.has(n.company)) continue
			const open = n.kind !== "module" || !n.company || expanded.has(n.company)
			include(open ? n.pos : n.dormant, n.kind === "core" ? n.radius + 24 : n.radius + 40)
		}
		for (const c of columns) include({ x: c.x, y: c.y }, 90)
		if (!isFinite(box.minX) || !size.w) return
		const zoom = clamp(Math.min(size.w / (box.maxX - box.minX + 48), size.h / (box.maxY - box.minY + 120)), MIN_ZOOM, 1.6)
		const center = { x: (box.minX + box.maxX) / 2, y: (box.minY + box.maxY) / 2 }
		const target = { zoom, pan: { x: -center.x * zoom, y: -center.y * zoom + 20 } }
		if (instant) {
			view.zoom = target.zoom
			view.pan = target.pan
			zoomLevel.value = view.zoom
		} else view.target = target
	}

	function localPoint(ev: MouseEvent): Vec {
		const rect = canvas.value!.getBoundingClientRect()
		return { x: ev.clientX - rect.left, y: ev.clientY - rect.top }
	}

	// ---- state helpers -----------------------------------------------------

	function visibility(n: SimNode) {
		return n.kind === "module" ? n.alpha * (0.2 + 0.8 * n.open) : n.alpha
	}

	function currentPos(n: SimNode): Vec {
		return n.kind === "module" ? lerpVec(n.dormant, n.pos, ease(n.open)) : n.pos
	}

	function currentRadius(n: SimNode) {
		const pulse = 1 + (reducedMotion ? 0 : 0.06 * Math.sin(time * 1.6 + n.phase))
		const scale = n.kind === "module" ? 0.45 + 0.55 * ease(n.open) : 1
		return n.radius * pulse * scale
	}

	function edgeAlpha(e: SimEdge) {
		return Math.min(visibility(e.a), visibility(e.b))
	}

	function control(e: SimEdge): Vec {
		const a = currentPos(e.a)
		const b = currentPos(e.b)
		const mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
		const dx = b.x - a.x
		const dy = b.y - a.y
		return { x: mid.x - dy * e.bend, y: mid.y + dx * e.bend }
	}

	function isFocused(e: SimEdge) {
		const h = hover.value
		if (h?.edge?.id === e.id) return true
		const focus = h?.node?.id ?? selected.value
		return focus === e.from || focus === e.to
	}

	function step(dt: number) {
		const k = 1 - Math.exp(-dt * 6)
		for (const n of nodes) {
			const shown = !n.company || !hidden.has(n.company)
			n.alpha += ((shown ? 1 : 0) - n.alpha) * k
			if (n.kind === "module") n.open += ((!n.company || expanded.has(n.company) ? 1 : 0) - n.open) * k
			n.flash *= Math.exp(-dt * 3)
		}
		if (view.target) {
			const t = view.target
			view.zoom += (t.zoom - view.zoom) * k
			view.pan = { x: view.pan.x + (t.pan.x - view.pan.x) * k, y: view.pan.y + (t.pan.y - view.pan.y) * k }
			zoomLevel.value = view.zoom
			if (Math.abs(t.zoom - view.zoom) < 0.001 && Math.hypot(t.pan.x - view.pan.x, t.pan.y - view.pan.y) < 0.5) view.target = null
		}
	}

	// ---- drawing -----------------------------------------------------------

	function draw() {
		if (!ctx) return
		const c = ctx
		c.setTransform(size.dpr, 0, 0, size.dpr, 0, 0)
		c.clearRect(0, 0, size.w, size.h)
		drawGhosts(c)

		c.save()
		c.translate(size.w / 2 + view.pan.x, size.h / 2 + view.pan.y)
		c.scale(view.zoom, view.zoom)
		drawColumns(c)
		for (const e of edges) drawEdge(c, e)
		c.globalCompositeOperation = "lighter"
		for (const e of edges) drawParticles(c, e)
		c.globalCompositeOperation = "source-over"
		for (const n of nodes) if (n.kind !== "core") drawNode(c, n)
		const core = byId.get("core")
		if (core) drawCore(c, core)
		c.restore()
	}

	function drawGhosts(c: CanvasRenderingContext2D) {
		const cx = size.w / 2
		const cy = size.h / 2
		const place = (g: Ghost) => ({
			x: cx + view.pan.x * g.depth + g.x * (0.6 + view.zoom * 0.4) * g.depth + Math.sin(time * 0.15 + g.phase) * 6,
			y: cy + view.pan.y * g.depth + g.y * (0.6 + view.zoom * 0.4) * g.depth + Math.cos(time * 0.12 + g.phase) * 6,
		})
		const placed = ghosts.map(place)
		c.lineWidth = 0.6
		for (const [i, j] of ghostLinks) {
			const g = ghosts[i]
			c.strokeStyle = `rgba(110, 160, 230, ${0.05 * g.depth})`
			c.beginPath()
			c.moveTo(placed[i].x, placed[i].y)
			c.lineTo(placed[j].x, placed[j].y)
			c.stroke()
		}
		ghosts.forEach((g, i) => {
			const twinkle = 0.5 + 0.5 * Math.sin(time * 0.8 + g.phase * 3)
			c.fillStyle = `rgba(150, 200, 255, ${(0.12 + 0.18 * twinkle) * g.depth})`
			c.beginPath()
			c.arc(placed[i].x, placed[i].y, g.r, 0, Math.PI * 2)
			c.fill()
		})
	}

	function drawColumns(c: CanvasRenderingContext2D) {
		if (!columns.length) return
		const bottom = Math.max(...nodes.map((n) => n.pos.y)) + 60
		c.textAlign = "center"
		c.textBaseline = "alphabetic"
		for (const col of columns) {
			c.strokeStyle = "rgba(120, 160, 220, 0.06)"
			c.lineWidth = 1 / view.zoom
			c.setLineDash([2, 6])
			c.beginPath()
			c.moveTo(col.x, col.y + 26)
			c.lineTo(col.x, bottom)
			c.stroke()
			c.setLineDash([])
			c.font = "600 10px Inter, system-ui, sans-serif"
			c.fillStyle = "rgba(170, 196, 235, 0.85)"
			c.fillText(col.title.toUpperCase(), col.x, col.y)
			c.font = "400 10px Inter, system-ui, sans-serif"
			c.fillStyle = "rgba(127, 147, 181, 0.75)"
			c.fillText(col.caption, col.x, col.y + 14)
		}
	}

	function drawEdge(c: CanvasRenderingContext2D, e: SimEdge) {
		const alpha = edgeAlpha(e)
		if (alpha < 0.01) return
		const a = currentPos(e.a)
		const b = currentPos(e.b)
		const ctrl = control(e)
		const focus = isFocused(e)
		c.strokeStyle = withAlpha(EDGE_STYLES[e.kind].color, alpha * (focus ? 0.6 : 0.16))
		c.lineWidth = (focus ? 1.3 : 0.8) / Math.sqrt(view.zoom)
		if (e.kind === "sync") c.setLineDash([3, 4])
		c.beginPath()
		c.moveTo(a.x, a.y)
		c.quadraticCurveTo(ctrl.x, ctrl.y, b.x, b.y)
		c.stroke()
		c.setLineDash([])
	}

	function drawParticles(c: CanvasRenderingContext2D, e: SimEdge) {
		const alpha = edgeAlpha(e)
		const open = Math.min(e.a.kind === "module" ? e.a.open : 1, e.b.kind === "module" ? e.b.open : 1)
		if (alpha < 0.05 || open < 0.5) return
		const a = currentPos(e.a)
		const b = currentPos(e.b)
		const ctrl = control(e)
		const color = EDGE_STYLES[e.kind].color
		const focus = isFocused(e) ? 1 : 0.7
		for (const p of e.particles) {
			const phase = (time * e.speed + p.offset) % 1
			if (phase < p.last) (e.flow === 1 ? e.b : e.a).flash = Math.min(1, (e.flow === 1 ? e.b : e.a).flash + 0.5)
			p.last = phase
			for (let tail = 0; tail < 5; tail++) {
				const t = clamp(phase - tail * 0.012, 0, 1)
				const pos = bezier(a, ctrl, b, e.flow === 1 ? t : 1 - t)
				c.fillStyle = withAlpha(color, alpha * focus * (1 - tail / 5) * fadeEnds(phase))
				c.beginPath()
				c.arc(pos.x, pos.y, (tail === 0 ? 1.7 : 1.2) / Math.sqrt(view.zoom), 0, Math.PI * 2)
				c.fill()
			}
		}
	}

	function drawNode(c: CanvasRenderingContext2D, n: SimNode) {
		const alpha = visibility(n)
		if (alpha < 0.01) return
		const pos = currentPos(n)
		const r = currentRadius(n)
		const active = selected.value === n.id || hover.value?.node?.id === n.id
		const glow = r * (3 + n.flash * 1.5)
		const pulse = reducedMotion ? 0.5 : 0.5 + 0.5 * Math.sin(time * 1.6 + n.phase)

		const g = c.createRadialGradient(pos.x, pos.y, r * 0.4, pos.x, pos.y, glow)
		g.addColorStop(0, withAlpha(n.color, alpha * (0.22 + 0.1 * pulse + n.flash * 0.2)))
		g.addColorStop(1, withAlpha(n.color, 0))
		c.fillStyle = g
		c.beginPath()
		c.arc(pos.x, pos.y, glow, 0, Math.PI * 2)
		c.fill()

		c.fillStyle = withAlpha("#071022", alpha)
		c.strokeStyle = withAlpha(n.color, alpha * (active ? 1 : 0.75))
		c.lineWidth = active ? 1.6 : 1
		c.beginPath()
		c.arc(pos.x, pos.y, r, 0, Math.PI * 2)
		c.fill()
		c.stroke()
		c.fillStyle = withAlpha(n.color, alpha * (0.55 + 0.35 * pulse + n.flash * 0.3))
		c.beginPath()
		c.arc(pos.x, pos.y, r * 0.38, 0, Math.PI * 2)
		c.fill()

		if (active) {
			c.strokeStyle = withAlpha(n.color, alpha * 0.45)
			c.lineWidth = 0.8
			c.beginPath()
			c.arc(pos.x, pos.y, r + 5, 0, Math.PI * 2)
			c.stroke()
		}

		const showLabel = n.kind === "company" || (n.kind === "module" ? n.open > 0.6 : true)
		if (showLabel && view.zoom > 0.5) {
			const size = n.kind === "company" ? 12 : 10
			c.font = `${n.kind === "company" ? 600 : 500} ${size}px Inter, system-ui, sans-serif`
			c.textAlign = "center"
			c.textBaseline = "top"
			c.fillStyle = `rgba(214, 228, 250, ${alpha * (n.kind === "company" || active ? 0.92 : 0.6)})`
			c.fillText(n.label, pos.x, pos.y + r + 7)
		}
	}

	function drawCore(c: CanvasRenderingContext2D, n: SimNode) {
		const r = currentRadius(n)
		const breathe = reducedMotion ? 0.5 : 0.5 + 0.5 * Math.sin(time * 1.1)
		const active = selected.value === n.id || hover.value?.node?.id === n.id

		const g = c.createRadialGradient(0, 0, r * 0.3, 0, 0, r * 4.2)
		g.addColorStop(0, withAlpha(n.color, 0.3 + 0.1 * breathe + n.flash * 0.1))
		g.addColorStop(0.45, withAlpha("#2dd4bf", 0.06))
		g.addColorStop(1, withAlpha(n.color, 0))
		c.fillStyle = g
		c.beginPath()
		c.arc(0, 0, r * 4.2, 0, Math.PI * 2)
		c.fill()

		c.save()
		c.rotate(time * 0.15)
		c.strokeStyle = withAlpha(n.color, 0.35)
		c.lineWidth = 0.8
		c.setLineDash([2, 6])
		c.beginPath()
		c.arc(0, 0, r + 12, 0, Math.PI * 2)
		c.stroke()
		c.rotate(-time * 0.35)
		c.setLineDash([14, 10])
		c.strokeStyle = withAlpha("#2dd4bf", 0.25)
		c.beginPath()
		c.arc(0, 0, r + 20, 0, Math.PI * 2)
		c.stroke()
		c.restore()
		c.setLineDash([])

		const body = c.createRadialGradient(-r * 0.3, -r * 0.3, 1, 0, 0, r)
		body.addColorStop(0, "#12304a")
		body.addColorStop(1, "#060d1c")
		c.fillStyle = body
		c.strokeStyle = withAlpha(n.color, active ? 1 : 0.8)
		c.lineWidth = active ? 1.8 : 1.2
		c.beginPath()
		c.arc(0, 0, r, 0, Math.PI * 2)
		c.fill()
		c.stroke()

		c.font = "600 11px Inter, system-ui, sans-serif"
		c.textAlign = "center"
		c.textBaseline = "middle"
		c.fillStyle = "rgba(226, 242, 255, 0.95)"
		c.fillText(n.label, 0, 0.5)
	}

	// ---- lifecycle ---------------------------------------------------------

	function loop(now: number) {
		const dt = Math.min((now - last) / 1000, 0.05)
		last = now
		time += dt * (reducedMotion ? 0.35 : 1)
		step(dt)
		draw()
		frame = requestAnimationFrame(loop)
	}

	function resize() {
		const el = canvas.value
		if (!el) return
		const rect = el.getBoundingClientRect()
		const first = size.w === 0
		size.w = rect.width
		size.h = rect.height
		size.dpr = Math.min(window.devicePixelRatio || 1, 2)
		el.width = Math.round(rect.width * size.dpr)
		el.height = Math.round(rect.height * size.dpr)
		if (first) reset(true)
	}

	function onVisibility() {
		cancelAnimationFrame(frame)
		if (!document.hidden) {
			last = performance.now()
			frame = requestAnimationFrame(loop)
		}
	}

	onMounted(() => {
		const el = canvas.value
		if (!el) return
		ctx = el.getContext("2d")
		observer = new ResizeObserver(resize)
		observer.observe(el)
		resize()
		el.addEventListener("pointerdown", onPointerDown)
		el.addEventListener("pointermove", onPointerMove)
		el.addEventListener("pointerup", onPointerUp)
		el.addEventListener("pointerleave", onPointerLeave)
		el.addEventListener("wheel", onWheel, { passive: false })
		document.addEventListener("visibilitychange", onVisibility)
		frame = requestAnimationFrame(loop)
	})

	onBeforeUnmount(() => {
		cancelAnimationFrame(frame)
		observer?.disconnect()
		document.removeEventListener("visibilitychange", onVisibility)
	})

	return { selected, expanded, hidden, hover, zoomLevel, load, select, toggleExpanded, zoomBy, reset: () => reset() }
}

// ---- pure helpers ----------------------------------------------------------

function makeGhosts(): Ghost[] {
	const ghosts: Ghost[] = []
	for (let i = 0; i < 150; i++) {
		const depth = i % 3 === 0 ? 0.35 : i % 3 === 1 ? 0.55 : 0.8
		const angle = hash(`g${i}a`) * Math.PI * 2
		const radius = Math.sqrt(hash(`g${i}r`)) * 900
		ghosts.push({ x: Math.cos(angle) * radius, y: Math.sin(angle) * radius, depth, r: 0.6 + hash(`g${i}s`) * 1.1, phase: hash(`g${i}p`) * Math.PI * 2 })
	}
	return ghosts
}

function linkGhosts(ghosts: Ghost[]) {
	const links: [number, number][] = []
	ghosts.forEach((a, i) => {
		for (let j = i + 1; j < ghosts.length; j++) {
			const b = ghosts[j]
			if (a.depth === b.depth && Math.hypot(a.x - b.x, a.y - b.y) < 120) links.push([i, j])
		}
	})
	return links
}

/** Deterministic 0..1 hash, so the layout is the same on every visit. */
function hash(text: string) {
	let h = 2166136261
	for (let i = 0; i < text.length; i++) {
		h ^= text.charCodeAt(i)
		h = Math.imul(h, 16777619)
	}
	return ((h >>> 0) % 10000) / 10000
}

function polar(angle: number, radius: number): Vec {
	return { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius }
}

function add(a: Vec, b: Vec): Vec {
	return { x: a.x + b.x, y: a.y + b.y }
}

function dist(a: Vec, b: Vec) {
	return Math.hypot(a.x - b.x, a.y - b.y)
}

function lerpVec(a: Vec, b: Vec, t: number): Vec {
	return { x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t }
}

function bezier(a: Vec, c: Vec, b: Vec, t: number): Vec {
	const u = 1 - t
	return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y }
}

function ease(t: number) {
	return t * t * (3 - 2 * t)
}

function fadeEnds(t: number) {
	return Math.min(1, t * 8, (1 - t) * 8)
}

function clamp(v: number, min: number, max: number) {
	return Math.min(max, Math.max(min, v))
}

function withAlpha(hex: string, alpha: number) {
	const n = parseInt(hex.slice(1), 16)
	return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${clamp(alpha, 0, 1).toFixed(3)})`
}
