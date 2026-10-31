export type Tone = "green" | "amber" | "red" | "blue" | "gray"

const TONES: Record<string, Record<string, Tone>> = {
	Employee: { Active: "green", Inactive: "red", Suspended: "amber", Left: "gray" },
	"Leave Application": { Open: "amber", Approved: "green", Rejected: "red", Cancelled: "gray" },
	Attendance: {
		Present: "green",
		"Work From Home": "blue",
		Absent: "red",
		"On Leave": "amber",
		"Half Day": "amber",
	},
	"Attendance Request": { "Work From Home": "blue", "On Duty": "green" },
	"Employee Checkin": { IN: "green", OUT: "blue" },
	"Shift Assignment": { Active: "green", Inactive: "gray" },
	"Payroll Entry": { Queued: "amber", Failed: "red" },
	"Salary Slip": { Withheld: "amber" },
	docstatus: { Draft: "gray", Submitted: "blue", Cancelled: "red", Expired: "gray" },
}

export function toneFor(doctype: string, status: string | null | undefined): Tone {
	if (!status) return "gray"
	return TONES[doctype]?.[status] || TONES.docstatus[status] || "gray"
}

export function docstatusLabel(docstatus: number) {
	return docstatus === 1 ? "Submitted" : docstatus === 2 ? "Cancelled" : "Draft"
}

/** Short codes for the attendance register, as in the design legend. */
export const ATTENDANCE_CODES: Record<string, string> = {
	Present: "P",
	Absent: "A",
	"On Leave": "L",
	"Half Day": "HD",
	"Work From Home": "WFH",
}

/** Attendance statuses shown in the attendance summaries (chips, legend, dashboard card). */
export const ATTENDANCE_SUMMARY_STATUSES = ["Present", "Absent", "On Leave"]

/** Leave applied for but not approved yet. Not an Attendance status: worked out from open Leave Applications. */
export const PENDING_LEAVE = { code: "PLA", label: "Pending leave approval", tone: "blue" as Tone }
/** An Attendance Request not submitted yet. Not an Attendance status: worked out from draft Attendance Requests. */
export const PENDING_REQUEST = { code: "ARR", label: "Attendance request pending", tone: "gray" as Tone }
