import { formatNumber } from "@/utils/format"

/** A one-line summary of a Leave Type's rules, from its real flags. */
export function leaveTypeRules(lt: Record<string, any>): string {
	const parts: string[] = []
	if (lt.max_leaves_allowed) parts.push(`Max ${formatNumber(lt.max_leaves_allowed)} d/yr`)
	if (lt.max_continuous_days_allowed) parts.push(`Up to ${lt.max_continuous_days_allowed} d at a time`)
	if (lt.is_carry_forward) parts.push("Carry forward")
	if (lt.allow_encashment) parts.push("Encashable")
	if (lt.is_earned_leave) parts.push("Earned")
	if (lt.is_lwp) parts.push("Without pay")
	if (lt.is_ppl) parts.push("Partially paid")
	if (lt.is_optional_leave) parts.push("Optional")
	if (lt.is_compensatory) parts.push("Compensatory")
	return parts.join(" · ")
}
