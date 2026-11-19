# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Whitelisted API methods for the IOU Dashboard in CentHR.

Integrates the legacy IOU and Loans DocType with Employee Advance (IOU applications) and Expense Claim
(IOU claims and expense claims) from HRMS, categorizing into:
- IOU Application
- IOU Claim Settlement – No Linked IOU
- IOU Claim Settlement – Linked IOU
- Salary Advance (an Employee Advance whose Purpose Type is Salary Advance)

The approve, reject, modify and pay actions run the SOP rules in centhr.iou.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate, strip_html
from frappe.utils.xlsxutils import build_xlsx_response

from centhr.customization.employee_advance_workflow import (
	FINANCE_1_ROLE,
	FINANCE_2_ROLE,
	STATE_APPROVED,
	STATE_FINANCE_1,
	STATE_HOD,
	STATE_OPEN,
	STATE_REJECTED,
)
from centhr.iou import actions as iou_actions
from centhr.iou import routing
from centhr.iou.advance import outstanding as advance_outstanding

IOU_DOCTYPE = "IOU and Loans"
ADVANCE_DOCTYPE = "Employee Advance"
CLAIM_DOCTYPE = "Expense Claim"
DASHBOARD_DOCTYPES = (IOU_DOCTYPE, ADVANCE_DOCTYPE, CLAIM_DOCTYPE)

# Employee Advance statuses where nothing is left to pay out, claim or return
ADVANCE_CLOSED_STATUSES = {"Claimed", "Returned", "Partly Claimed and Returned", "Cancelled"}

CATEGORY_APPLICATION = "IOU Application"
CATEGORY_SETTLEMENT_NO_LINK = "IOU Claim Settlement – No Linked IOU"
CATEGORY_SETTLEMENT_LINKED = "IOU Claim Settlement – Linked IOU"
CATEGORY_SALARY_ADVANCE = "Salary Advance"

# Each record's advance type is its category; the filter always offers all of them
ADVANCE_TYPES = (
	CATEGORY_APPLICATION,
	CATEGORY_SETTLEMENT_LINKED,
	CATEGORY_SETTLEMENT_NO_LINK,
	CATEGORY_SALARY_ADVANCE,
)

APPROVED = "Approved"
PENDING = "Pending"
REJECTED = "Rejected"
NOT_REQUIRED = "Not Required"

# Records still waiting for one of their approvers
IOU_PENDING_STATUSES = {"Pending", "Approved by Manager", "Approved by Finance 1"}
ADVANCE_PENDING_STATES = {STATE_OPEN, STATE_HOD, STATE_FINANCE_1}

# The Employee Advance Approval workflow state each approver moves the advance to
ADVANCE_STAGES = (("hod", STATE_HOD), ("finance_1", STATE_FINANCE_1), ("finance_2", STATE_APPROVED))

# The top cards drill down to these rows
FOCUS_FILTERS = {
	"advances": lambda r: r["doctype"] == ADVANCE_DOCTYPE,
	"pending": lambda r: r["is_pending_approval"],
	"overdue": lambda r: r["is_overdue"],
	"mine": lambda r: bool(r.get("actions")),
}

EXPORT_COLUMNS = [
	(_("Category"), "category"),
	(_("Reference No"), "name"),
	(_("Linked Advance"), "employee_advance"),
	(_("Linked IOU"), "linked_iou"),
	(_("Advance Type"), "advance_type"),
	(_("Employee ID"), "employee"),
	(_("Employee Name"), "employee_name"),
	(_("Department"), "department"),
	(_("Company"), "company"),
	(_("Amount"), "amount"),
	(_("Application Date"), "posting_date"),
	(_("Due Date"), "due_date"),
	(_("Status"), "status"),
	(_("HOD Approver"), "hod_approver_display"),
	(_("Finance 1 Approver"), "finance_1_display"),
	(_("Finance 2 Approver"), "finance_2_display"),
]

IOU_FIELDS = [
	"name",
	"type",
	"status",
	"posting_date",
	"employee",
	"employee_name",
	"department",
	"company",
	"advance_amount",
	"purpose_type",
	"tenure",
	"purpose",
	"outstanding_amount",
	"repay_unclaimed_amount_from_salary",
	"total_claimed_amount",
	"amount",
	"settlement_amount",
	"claim_method",
	"employee_advance",
	"reporting_manager",
	"reporting_manager_name",
	"hod_approved_datetime",
	"reason_for_manager_rejection",
	"finance",
	"finance_name",
	"finance_approved_datetime",
	"reason_for_finance_one_rejection",
	"finance_2",
	"finance_name_two",
	"finance_2_approved_datetime",
	"pending_approval_from",
	"docstatus",
	"creation",
]

ADVANCE_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"company",
	"posting_date",
	"purpose",
	"advance_amount",
	"paid_amount",
	"claimed_amount",
	"return_amount",
	"pending_amount",
	"status",
	"docstatus",
	"creation",
]

# Custom or optional Employee Advance fields, read only when the site has them
OPTIONAL_ADVANCE_FIELDS = (
	"iou_and_loans",
	"due_date",
	"expected_return_date",
	"repay_unclaimed_amount_from_salary",
	"workflow_state",
	"line_manager",
	"purpose_type",
	"current_approver",
	"proxy_approver",
	"hod_approved_by",
	"finance_1_approved_by",
	"finance_2_approved_by",
	"rejected_by",
	"rejected_stage",
	"rejection_reason",
)

CLAIM_FIELDS = [
	"name",
	"employee",
	"employee_name",
	"department",
	"company",
	"posting_date",
	"currency",
	"remark",
	"total_claimed_amount",
	"grand_total",
	"total_amount_reimbursed",
	"status",
	"approval_status",
	"docstatus",
	"creation",
]

# Custom Expense Claim fields, read only when the site has them
OPTIONAL_CLAIM_FIELDS = (
	"iou_and_loans",
	"workflow_state",
	"line_manager",
	"claim_from_pocket",
	"current_approver",
	"proxy_approver",
	"hod_approved_by",
	"finance_1_approved_by",
	"rejected_by",
	"rejected_stage",
	"rejection_reason",
)


@frappe.whitelist()
def get_iou_dashboard_data(
	employee: str | None = None,
	company: str | None = None,
	advance_type: str | None = None,
	status: str | None = None,
	closed: int | str = 0,
	category: str | None = None,
	search: str | None = None,
	focus: str | None = None,
) -> dict:
	"""Fetches unified IOU and Employee Advance records with summary statistics and filter options."""
	records = _fetch_all_records(employee, company)
	# Open transactions by default; "Closed Transactions" shows only the completed ones
	records = [r for r in records if r["is_closed"] == bool(cint(closed))]

	# Filter options come from every record the user can see, so they don't shrink as filters change
	available_statuses = sorted({r["status"] for r in records if r.get("status")})

	search_term = (search or "").strip().lower()
	matching = [r for r in records if _matches(r, advance_type, status, search_term)]

	# The cards show totals for the current filters; the category and the focus are drill-downs
	stats = _compute_stats(matching)
	focus_filter = FOCUS_FILTERS.get(focus or "")
	filtered = [
		r
		for r in matching
		if (not category or r["category"] == category) and (not focus_filter or focus_filter(r))
	]

	return {
		"records": filtered,
		"stats": stats,
		"advance_types": list(ADVANCE_TYPES),
		"statuses": available_statuses,
	}


@frappe.whitelist()
def get_iou_detail(name: str, doctype: str = IOU_DOCTYPE) -> dict:
	"""Fetches full details for a single record including child expense lines."""
	if doctype not in DASHBOARD_DOCTYPES:
		frappe.throw(_("Invalid document type {0}").format(doctype))

	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	detail = doc.as_dict()
	if doctype != IOU_DOCTYPE:
		detail["actions"] = iou_actions.available_actions(doc)
	if doctype == ADVANCE_DOCTYPE:
		detail["outstanding_amount"] = advance_outstanding(doc) if doc.docstatus == 1 else 0.0
	return detail


@frappe.whitelist(methods=["POST"])
def export_iou_records(
	employee: str | None = None,
	company: str | None = None,
	advance_type: str | None = None,
	status: str | None = None,
	closed: int | str = 0,
	category: str | None = None,
	search: str | None = None,
	focus: str | None = None,
	names: list[str] | str | None = None,
):
	"""Exports the filtered or selected IOU dashboard rows as an Excel spreadsheet."""
	rows = get_iou_dashboard_data(
		employee=employee,
		company=company,
		advance_type=advance_type,
		status=status,
		closed=closed,
		category=category,
		search=search,
		focus=focus,
	)["records"]

	names = frappe.parse_json(names) if isinstance(names, str) else names
	if names:
		name_set = set(names)
		rows = [r for r in rows if r["name"] in name_set]

	for r in rows:
		r["hod_approver_display"] = _approver_display(r["approvers"]["hod"])
		r["finance_1_display"] = _approver_display(r["approvers"]["finance_1"])
		r["finance_2_display"] = _approver_display(r["approvers"]["finance_2"])

	excel_data = [[label for label, _key in EXPORT_COLUMNS]]
	excel_data += [[r.get(key) for _label, key in EXPORT_COLUMNS] for r in rows]

	build_xlsx_response(excel_data, f"IOU_Dashboard_{nowdate()}")


def _approver_display(approver: dict) -> str:
	name = approver.get("name") or approver.get("user")
	return f"{name} ({approver['status']})" if name else approver["status"]


def _matches(row: dict, advance_type: str | None, status: str | None, search_term: str) -> bool:
	if advance_type and row.get("advance_type") != advance_type:
		return False
	if status and row.get("status") != status:
		return False
	if search_term:
		searchable = " ".join(
			str(row.get(f) or "")
			for f in (
				"name",
				"employee",
				"employee_name",
				"advance_type",
				"purpose",
				"employee_advance",
				"linked_iou",
				"status",
			)
		).lower()
		return search_term in searchable
	return True


def _fetch_all_records(employee: str | None = None, company: str | None = None) -> list[dict]:
	"""Retrieves and normalizes records from both IOU and Loans and Employee Advance."""
	records: list[dict] = []
	# IOU records that link to an advance, so the advance row can show its IOU
	iou_by_advance: dict[str, str] = {}
	filters = {}
	if employee:
		filters["employee"] = employee
	if company:
		filters["company"] = company
	today = getdate(nowdate())

	if frappe.has_permission(IOU_DOCTYPE, "read"):
		for row in frappe.get_list(IOU_DOCTYPE, fields=IOU_FIELDS, filters=filters, limit_page_length=0):
			record = _normalize_iou_record(row, today)
			records.append(record)
			if record["employee_advance"]:
				iou_by_advance.setdefault(record["employee_advance"], record["name"])

	if frappe.has_permission(ADVANCE_DOCTYPE, "read"):
		meta = frappe.get_meta(ADVANCE_DOCTYPE)
		fields = [*ADVANCE_FIELDS, *(f for f in OPTIONAL_ADVANCE_FIELDS if meta.has_field(f))]

		advances = frappe.get_list(ADVANCE_DOCTYPE, fields=fields, filters=filters, limit_page_length=0)
		approvals, user_names = _get_workflow_approvals(advances)

		# Every advance is its own row, also when an IOU record links to it
		for row in advances:
			approvals_of_row = approvals.get(row["name"], {})
			records.append(_normalize_employee_advance(row, today, iou_by_advance, approvals_of_row, user_names))

	if frappe.has_permission(CLAIM_DOCTYPE, "read"):
		meta = frappe.get_meta(CLAIM_DOCTYPE)
		fields = [*CLAIM_FIELDS, *(f for f in OPTIONAL_CLAIM_FIELDS if meta.has_field(f))]
		claims = frappe.get_list(
			CLAIM_DOCTYPE,
			fields=fields,
			filters={**filters, "docstatus": ["<", 2]},
			limit_page_length=0,
		)
		linked = _claim_advances([row["name"] for row in claims])
		claim_users = _user_names(claims)
		records.extend(_normalize_expense_claim(row, linked.get(row["name"]), claim_users) for row in claims)

	records.sort(key=lambda r: (r["posting_date"] or "", str(r.get("creation") or "")), reverse=True)
	return records


def _normalize_iou_record(row: dict, today) -> dict:
	"""Maps an IOU and Loans record into the standardized dashboard structure."""
	iou_type = row.get("type") or CATEGORY_APPLICATION
	linked_advance = row.get("employee_advance")

	if iou_type == CATEGORY_APPLICATION:
		category = CATEGORY_APPLICATION
		amount = flt(row.get("advance_amount") or row.get("amount"))
	elif iou_type == "IOU Claim Settlement":
		category = CATEGORY_SETTLEMENT_LINKED if linked_advance else CATEGORY_SETTLEMENT_NO_LINK
		amount = flt(row.get("total_claimed_amount") or row.get("settlement_amount") or row.get("amount"))
	else:
		category = CATEGORY_SETTLEMENT_NO_LINK
		amount = flt(row.get("amount") or row.get("settlement_amount"))

	# Tenure is in days; without it the record has no due date
	due_date = None
	if row.get("posting_date") and cint(row.get("tenure")):
		due_date = add_days(getdate(row["posting_date"]), cint(row["tenure"]))

	status = _doc_status(row)
	outstanding = flt(row.get("outstanding_amount"))
	if status == "Cancelled":
		is_closed = True
	elif category == CATEGORY_APPLICATION:
		# A paid application stays open until the money is settled
		is_closed = status == "Paid" and not outstanding
	else:
		is_closed = status == "Paid"

	return {
		"doctype": IOU_DOCTYPE,
		"name": row["name"],
		"category": category,
		"advance_type": category,
		"employee": row.get("employee"),
		"employee_name": row.get("employee_name") or row.get("employee"),
		"department": row.get("department"),
		"company": row.get("company"),
		"amount": amount,
		"outstanding_amount": outstanding,
		"posting_date": _date_str(row.get("posting_date")),
		"due_date": _date_str(due_date),
		"status": status,
		"is_closed": is_closed,
		"is_overdue": bool(not is_closed and due_date and due_date < today),
		"is_pending_approval": row.get("docstatus") != 2 and row.get("status") in IOU_PENDING_STATUSES,
		"purpose": row.get("purpose"),
		"employee_advance": linked_advance,
		"linked_iou": None,
		"approvers": _iou_approvers(row),
		"claim_method": row.get("claim_method"),
		"repay_from_salary": row.get("repay_unclaimed_amount_from_salary"),
		"creation": row.get("creation"),
	}


def _iou_approvers(row: dict) -> dict:
	"""HOD → Finance 1 → Finance 2 approval state, read from the IOU's own approval fields."""
	stages = (
		("hod", "reporting_manager", "reporting_manager_name", "hod_approved_datetime", "reason_for_manager_rejection"),
		("finance_1", "finance", "finance_name", "finance_approved_datetime", "reason_for_finance_one_rejection"),
		("finance_2", "finance_2", "finance_name_two", "finance_2_approved_datetime", None),
	)
	approvers = {}
	for key, user_field, name_field, datetime_field, reason_field in stages:
		reason = row.get(reason_field) if reason_field else None
		if row.get(datetime_field):
			state = APPROVED
		elif reason:
			state = REJECTED
		else:
			state = PENDING
		approvers[key] = {
			"user": row.get(user_field),
			"name": row.get(name_field),
			"status": state,
			"datetime": row.get(datetime_field),
			"reason": reason,
		}
	return approvers


def _normalize_employee_advance(
	row: dict, today, iou_by_advance: dict[str, str], approvals: dict[str, dict], user_names: dict[str, str]
) -> dict:
	"""Maps a standard HRMS Employee Advance into the dashboard structure."""
	due_value = row.get("due_date") or row.get("expected_return_date")
	due_date = getdate(due_value) if due_value else None
	workflow_state = row.get("workflow_state")
	status = _doc_status(row)
	# A draft shows how far its approval has come
	if row.get("docstatus") == 0 and workflow_state:
		status = workflow_state
	is_closed = status in ADVANCE_CLOSED_STATUSES or status == STATE_REJECTED
	category = CATEGORY_SALARY_ADVANCE if row.get("purpose_type") == CATEGORY_SALARY_ADVANCE else CATEGORY_APPLICATION

	return {
		"doctype": ADVANCE_DOCTYPE,
		"name": row["name"],
		"category": category,
		"advance_type": category,
		"employee": row.get("employee"),
		"employee_name": row.get("employee_name") or row.get("employee"),
		"department": row.get("department"),
		"company": row.get("company"),
		"amount": flt(row.get("advance_amount")),
		# HRMS's pending_amount is what is still to be paid out, not what is still to be settled
		"outstanding_amount": advance_outstanding(row) if row.get("docstatus") == 1 else 0.0,
		"paid_amount": flt(row.get("paid_amount")),
		"claimed_amount": flt(row.get("claimed_amount")),
		"posting_date": _date_str(row.get("posting_date")),
		"due_date": _date_str(due_date),
		"status": status,
		"is_closed": is_closed,
		"is_overdue": bool(not is_closed and due_date and due_date < today),
		"is_pending_approval": row.get("docstatus") == 0 and workflow_state in ADVANCE_PENDING_STATES,
		"purpose": row.get("purpose"),
		"employee_advance": row["name"],
		# A migrated advance keeps its CentHR IOU link; otherwise use the IOU record that links to it
		"linked_iou": row.get("iou_and_loans") or iou_by_advance.get(row["name"]),
		"approvers": _advance_approvers(row, approvals, user_names),
		"repay_from_salary": row.get("repay_unclaimed_amount_from_salary", 0),
		"purpose_type": row.get("purpose_type"),
		"current_approver": row.get("current_approver"),
		"rejection_reason": row.get("rejection_reason"),
		"actions": iou_actions.available_actions(frappe._dict(row, doctype=ADVANCE_DOCTYPE)),
		"creation": row.get("creation"),
	}


def _normalize_expense_claim(row: dict, advance: dict | None, user_names: dict[str, str]) -> dict:
	"""Maps an Expense Claim: an IOU claim when it settles an IOU, else an expense claim from pocket."""
	status = _doc_status(row)
	if row.get("docstatus") == 0 and row.get("workflow_state"):
		status = row["workflow_state"]
	is_closed = status in ("Paid", "Cancelled", STATE_REJECTED)
	amount = flt(row.get("total_claimed_amount"))
	from_iou = flt(advance["allocated_amount"]) if advance else 0.0
	category = CATEGORY_SETTLEMENT_LINKED if advance else CATEGORY_SETTLEMENT_NO_LINK

	return {
		"doctype": CLAIM_DOCTYPE,
		"name": row["name"],
		"category": category,
		"advance_type": category,
		"employee": row.get("employee"),
		"employee_name": row.get("employee_name") or row.get("employee"),
		"department": row.get("department"),
		"company": row.get("company"),
		"amount": amount,
		# SOP: the part that settles the IOU (yellow) and the part paid to the employee (blue)
		"amount_from_iou": from_iou,
		"amount_from_pocket": max(amount - from_iou, 0.0),
		# Still to be paid to the employee
		"outstanding_amount": max(flt(row.get("grand_total")) - flt(row.get("total_amount_reimbursed")), 0.0)
		if row.get("docstatus") == 1
		else 0.0,
		"posting_date": _date_str(row.get("posting_date")),
		"due_date": None,
		"status": status,
		"is_closed": is_closed,
		"is_overdue": False,
		"is_pending_approval": row.get("docstatus") == 0 and row.get("workflow_state") in (STATE_OPEN, STATE_HOD),
		"purpose": row.get("remark"),
		"employee_advance": advance["employee_advance"] if advance else None,
		"linked_iou": row.get("iou_and_loans"),
		"approvers": _claim_approvers(row, user_names),
		"current_approver": row.get("current_approver"),
		"rejection_reason": row.get("rejection_reason"),
		"actions": iou_actions.available_actions(frappe._dict(row, doctype=CLAIM_DOCTYPE)),
		"creation": row.get("creation"),
	}


def _claim_advances(claims: list[str]) -> dict[str, dict]:
	"""{claim: {employee_advance, allocated_amount}} for the claims that settle an IOU."""
	if not claims:
		return {}
	rows = frappe.get_all(
		"Expense Claim Advance",
		filters={"parenttype": CLAIM_DOCTYPE, "parent": ["in", claims], "allocated_amount": [">", 0]},
		fields=["parent", "employee_advance", "allocated_amount"],
	)
	return {row.parent: row for row in rows}


def _user_names(rows: list[dict]) -> dict[str, str]:
	users = {
		row.get(field)
		for row in rows
		for field in ("current_approver", "hod_approved_by", "finance_1_approved_by", "rejected_by")
		if row.get(field)
	}
	if not users:
		return {}
	return dict(frappe.get_all("User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"], as_list=True))


def _claim_approvers(row: dict, user_names: dict[str, str]) -> dict:
	"""HOD → Finance 1 state of a claim, from the fields kept by centhr.iou.routing. Claims have no Finance 2 step."""
	approvers = {
		"hod": _stage_approver(row, routing.HOD, user_names),
		"finance_1": _stage_approver(row, routing.FINANCE_1, user_names),
	}
	approvers["finance_2"] = {"user": None, "name": None, "status": NOT_REQUIRED, "datetime": None, "reason": None}
	return approvers


def _stage_approver(row: dict, stage: str, user_names: dict[str, str]) -> dict:
	approved_by = row.get(routing.APPROVED_BY_FIELD[stage])
	if approved_by or row.get("docstatus") == 1:
		# A migrated claim is submitted without any approver recorded
		user, status, reason = approved_by, APPROVED, None
	elif row.get("rejected_stage") == stage:
		user, status, reason = row.get("rejected_by"), REJECTED, row.get("rejection_reason")
	else:
		waiting_here = routing.PENDING_STAGE[CLAIM_DOCTYPE].get(row.get("workflow_state") or STATE_OPEN) == stage
		user, status, reason = (row.get("current_approver") if waiting_here else None), PENDING, None
	return {"user": user, "name": user_names.get(user) or user, "status": status, "datetime": None, "reason": reason}


def _get_workflow_approvals(advances: list[dict]) -> tuple[dict[str, dict], dict[str, str]]:
	"""Who moved each advance to each workflow state, and when.

	Frappe's apply_workflow adds a "Workflow" comment with the new state for every step. Returns
	{advance: {state: latest comment}} and {user: full name} for the approvers and line managers.
	"""
	names = [row["name"] for row in advances if row.get("workflow_state")]
	approvals: dict[str, dict] = {}
	users = {
		row.get(field)
		for row in advances
		for field in ("line_manager", "current_approver", "hod_approved_by", "finance_1_approved_by", "finance_2_approved_by", "rejected_by")
		if row.get(field)
	}

	if names:
		comments = frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": ADVANCE_DOCTYPE,
				"reference_name": ["in", names],
				"comment_type": "Workflow",
			},
			fields=["reference_name", "content", "owner", "creation"],
			order_by="creation asc",
		)
		for comment in comments:
			state = strip_html(comment.content or "").strip()
			approvals.setdefault(comment.reference_name, {})[state] = comment
			users.add(comment.owner)

	user_names = (
		dict(frappe.get_all("User", filters={"name": ["in", list(users)]}, fields=["name", "full_name"], as_list=True))
		if users
		else {}
	)
	return approvals, user_names


def _advance_approvers(row: dict, comments: dict[str, dict], user_names: dict[str, str]) -> dict:
	"""HOD → Finance 1 → Finance 2 state of an advance, read from the Employee Advance Approval workflow."""
	workflow_state = row.get("workflow_state")
	if not workflow_state:
		no_approval = {"name": None, "status": NOT_REQUIRED}
		return {key: dict(no_approval) for key, _state in ADVANCE_STAGES}

	stage_of_key = {"hod": routing.HOD, "finance_1": routing.FINANCE_1, "finance_2": routing.FINANCE_2}
	waiting_stage = routing.PENDING_STAGE[ADVANCE_DOCTYPE].get(workflow_state) if row.get("docstatus") == 0 else None
	pending_role = {"hod": None, "finance_1": FINANCE_1_ROLE, "finance_2": FINANCE_2_ROLE}
	# A migrated advance is submitted as Approved without any workflow comments
	fully_approved = workflow_state == STATE_APPROVED or row.get("docstatus") == 1
	rejection = comments.get(STATE_REJECTED) if workflow_state == STATE_REJECTED else None

	approvers = {}
	for key, state in ADVANCE_STAGES:
		stage = stage_of_key[key]
		comment = comments.get(state)
		recorded = row.get(routing.APPROVED_BY_FIELD[stage])
		reason = None
		if recorded or comment or fully_approved:
			user, status = recorded or (comment.owner if comment else None), APPROVED
			when = comment.creation if comment else None
		elif row.get("rejected_stage") == stage:
			user, status, when, reason = row.get("rejected_by"), REJECTED, None, row.get("rejection_reason")
			rejection = None
		elif rejection:
			# Rejected before the approval fields existed: the first approver who has not approved rejected it
			user, status, when = rejection.owner, REJECTED, rejection.creation
			rejection = None
		else:
			user, status, when = (row.get("current_approver") if waiting_stage == stage else None), PENDING, None
			if not user and key == "hod":
				user = row.get("line_manager")

		approvers[key] = {
			"user": user,
			"name": user_names.get(user) or user or (pending_role[key] if status == PENDING else None),
			"status": status,
			"datetime": when,
			"reason": reason,
		}
	return approvers


def _doc_status(row: dict) -> str:
	"""A cancelled document keeps its last status value, so docstatus decides first."""
	if row.get("docstatus") == 2:
		return "Cancelled"
	return row.get("status") or ("Draft" if row.get("docstatus") == 0 else "Submitted")


def _date_str(value) -> str | None:
	return str(value) if value else None


def _compute_stats(rows: list[dict]) -> dict:
	"""Computes count and total amount for each category, overall, and the top cards."""
	keys = {
		CATEGORY_APPLICATION: "iou_application",
		CATEGORY_SETTLEMENT_NO_LINK: "settlement_no_link",
		CATEGORY_SETTLEMENT_LINKED: "settlement_linked",
		CATEGORY_SALARY_ADVANCE: "salary_advance",
	}
	stats = {
		key: {"count": 0, "amount": 0.0}
		for key in (*keys.values(), "total", "advances", "pending_approval", "overdue", "waiting_for_me")
	}

	def add(key: str, amount: float) -> None:
		stats[key]["count"] += 1
		stats[key]["amount"] += amount

	for r in rows:
		amount = flt(r.get("amount"))
		for key in (keys.get(r["category"]), "total"):
			if key:
				add(key, amount)
		if r["doctype"] == ADVANCE_DOCTYPE:
			add("advances", amount)
		if r["is_pending_approval"]:
			add("pending_approval", amount)
		if r["is_overdue"]:
			add("overdue", flt(r.get("outstanding_amount")) or amount)
		if r.get("actions"):
			add("waiting_for_me", amount)

	return stats


# ---------------------------------------------------------------- actions (SOP approval steps)


@frappe.whitelist(methods=["POST"])
def apply_iou_action(
	doctype: str,
	name: str,
	action: str,
	reason: str | None = None,
	advance_amount: float | None = None,
	expenses: str | list | None = None,
) -> dict:
	"""Approve, Reject (with a reason) or Modify an IOU application or claim."""
	if action == iou_actions.APPROVE:
		iou_actions.approve(doctype, name)
	elif action == iou_actions.REJECT:
		iou_actions.reject(doctype, name, reason)
	elif action == iou_actions.MODIFY:
		iou_actions.modify(doctype, name, advance_amount=advance_amount, expenses=expenses)
	else:
		frappe.throw(_("Unknown action {0}").format(action))
	return get_iou_detail(name, doctype)


@frappe.whitelist(methods=["POST"])
def pay_iou(
	doctype: str,
	name: str,
	bank_account: str,
	reference_no: str | None = None,
	payment_advice: str | None = None,
) -> dict:
	"""Finance 2 pays an approved IOU, or Finance 1 pays the from-pocket part of an approved claim."""
	from centhr.iou.advance import pay_advance
	from centhr.iou.claim import pay_claim

	if doctype == ADVANCE_DOCTYPE:
		payment_entry = pay_advance(name, bank_account, reference_no, payment_advice)
	elif doctype == CLAIM_DOCTYPE:
		payment_entry = pay_claim(name, bank_account, reference_no)
	else:
		frappe.throw(_("Invalid document type {0}").format(doctype))
	return {"payment_entry": payment_entry, "detail": get_iou_detail(name, doctype)}


@frappe.whitelist()
def get_payment_accounts(company: str) -> list[dict]:
	"""Bank and cash accounts the IOU can be paid from (SOP: drop-down list of bank accounts)."""
	return frappe.get_all(
		"Account",
		filters={"company": company, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "account_type", "account_currency"],
		order_by="account_type asc, account_name asc",
	)


@frappe.whitelist()
def get_expense_claim_types() -> list[str]:
	return frappe.get_all("Expense Claim Type", pluck="name", order_by="name")
