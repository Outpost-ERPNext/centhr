<template>
	<section class="rounded-5 border border-ch-line bg-ch-surface p-4 sm:p-5">
		<h3 class="mb-4 text-[14px] font-medium text-ch-ink">Activity</h3>
		<ol class="flex flex-col">
			<li v-for="(item, index) in items" :key="item.key" class="relative flex gap-3 pb-4">
				<span
					v-if="index < items.length - 1"
					class="absolute left-[13px] top-7 h-[calc(100%-24px)] w-px bg-ch-line"
					aria-hidden="true"
				/>
				<span
					class="z-[1] flex size-7 shrink-0 items-center justify-center rounded-full bg-ch-subtle text-ch-ink-2"
				>
					<span class="size-3.5" :class="item.icon" />
				</span>
				<div class="min-w-0 flex-1 pt-1">
					<div v-if="item.type === 'comment'" class="rounded-4 border border-ch-line bg-ch-sb px-3 py-2">
						<div class="mb-1 flex items-center justify-between gap-2 text-[12px] text-ch-ink-3">
							<span class="font-medium text-ch-ink-2">{{ item.by }}</span>
							<span :title="item.at">{{ timeAgo(item.at) }}</span>
						</div>
						<div class="prose prose-sm max-w-none text-[13px] text-ch-ink" v-html="item.html" />
					</div>
					<div v-else class="flex flex-wrap items-baseline justify-between gap-x-2 text-[13px]">
						<span class="text-ch-ink-2">
							<span class="font-medium text-ch-ink">{{ item.by }}</span> {{ item.text }}
						</span>
						<span class="text-[12px] text-ch-ink-3" :title="item.at">{{ timeAgo(item.at) }}</span>
					</div>
				</div>
			</li>
		</ol>

		<div v-if="canComment" class="mt-1 flex flex-col gap-2">
			<Textarea
				v-model="comment"
				placeholder="Add a comment"
				:rows="2"
				aria-label="Add a comment"
				@keydown.ctrl.enter="post"
				@keydown.meta.enter="post"
			/>
			<div class="flex items-center justify-between">
				<span class="text-[12px] text-ch-ink-4">Ctrl + Enter to post</span>
				<Button size="sm" label="Comment" :loading="posting" :disabled="!comment.trim()" @click="post" />
			</div>
		</div>
	</section>
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { Button, Textarea } from "frappe-ui"
import { addComment, type DocInfo } from "@/data/doc"
import { fieldLabel } from "@/data/meta"
import { timeAgo } from "@/utils/format"

const props = defineProps<{
	doctype: string
	doc: Record<string, any>
	docinfo: DocInfo | null
	canComment?: boolean
}>()
const emit = defineEmits<{ commented: [] }>()

const comment = ref("")
const posting = ref(false)

interface Item {
	key: string
	type: "comment" | "event"
	icon: string
	by: string
	at: string
	text?: string
	html?: string
}

const items = computed<Item[]>(() => {
	const list: Item[] = [
		{
			key: "created",
			type: "event",
			icon: "lucide-file-plus",
			by: props.doc.owner,
			at: props.doc.creation,
			text: "created this record",
		},
	]
	for (const v of props.docinfo?.versions || []) {
		const text = describeVersion(v.data)
		if (text) list.push({ key: v.name, type: "event", icon: "lucide-pencil", by: v.owner, at: v.creation, text })
	}
	for (const c of props.docinfo?.comments || []) {
		list.push({
			key: c.name,
			type: "comment",
			icon: "lucide-message-square",
			by: c.owner,
			at: c.creation,
			html: c.content,
		})
	}
	return list.sort((a, b) => (a.at < b.at ? -1 : 1))
})

function describeVersion(raw: string) {
	try {
		const data = JSON.parse(raw)
		const changed: [string, any, any][] = data.changed || []
		const status = changed.find(([field]) => field === "docstatus")
		if (status) return status[2] === 1 ? "submitted this record" : status[2] === 2 ? "cancelled this record" : ""
		if (!changed.length) return data.added?.length || data.removed?.length ? "changed table rows" : ""
		const parts = changed
			.slice(0, 3)
			.map(([field, , value]) => `${fieldLabel(props.doctype, field)} to “${value ?? ""}”`)
		return `changed ${parts.join(", ")}${changed.length > 3 ? ` and ${changed.length - 3} more` : ""}`
	} catch {
		return ""
	}
}

async function post() {
	const content = comment.value.trim()
	if (!content || posting.value) return
	posting.value = true
	try {
		await addComment(props.doctype, props.doc.name, escapeHtml(content).replace(/\n/g, "<br>"))
		comment.value = ""
		emit("commented")
	} finally {
		posting.value = false
	}
}

function escapeHtml(text: string) {
	const div = document.createElement("div")
	div.textContent = text
	return div.innerHTML
}
</script>
