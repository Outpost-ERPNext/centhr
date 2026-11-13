export interface OrgMaster {
	label: string
	icon: string
	route: string
	doctype: string
	description: string
}

/** Organisation masters, shown as cards on the Org Master page. */
export const ORG_MASTERS: OrgMaster[] = [
	{ label: "Department", icon: "lucide-building-2", route: "/departments", doctype: "Department", description: "Departments and their hierarchy" },
	{ label: "Grade", icon: "lucide-award", route: "/grades", doctype: "Employee Grade", description: "Employee grades and default salary structures" },
	{ label: "Designation", icon: "lucide-briefcase", route: "/designations", doctype: "Designation", description: "Job titles used across the organisation" },
	{ label: "Cost Center", icon: "lucide-landmark", route: "/cost-centers", doctype: "Cost Center", description: "Cost centers for payroll accounting" },
	{ label: "Channel", icon: "lucide-radio-tower", route: "/channels", doctype: "Channel", description: "Business channels employees work in" },
	{ label: "Employment Type", icon: "lucide-id-card", route: "/employment-types", doctype: "Employment Type", description: "Permanent, contract, intern and other types" },
	{ label: "Gender", icon: "lucide-venus-and-mars", route: "/genders", doctype: "Gender", description: "Gender options for employee records" },
	{ label: "Salary Structure", icon: "lucide-layers", route: "/salary-structures", doctype: "Salary Structure", description: "Earnings and deductions templates" },
]

export const ORG_MASTER_CRUMB = { label: "Org Master", route: "/org-master" }

export function isOrgMaster(doctype: string) {
	return ORG_MASTERS.some((m) => m.doctype === doctype)
}
