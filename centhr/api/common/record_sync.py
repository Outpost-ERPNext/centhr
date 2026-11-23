# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Shared code for the Leave Allocation, Employee Checkin, Shift Type and IOU (Employee Advance,
Expense Claim, Payment Entry) APIs.

The files in centhr/api/post, update and delete hold the hooks and background jobs of each
doctype and call `enqueue_job`, `sync_record` and `delete_record` from here.

`sync_record` POSTs the record when it is not on the target yet and PUTs it otherwise
(including submit and cancel), so a create that failed is sent again by the next update.
The target-side name of a record is taken from its successful POST in CentHR API Logger,
or from the migration tool's log when the record came from the CentHR site. Doctypes named
by hand (Shift Type) keep their name everywhere.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

from centhr.api.common.remote_links import RemoteLinks
from centhr.api.common.target_client import TargetClient
from centhr.api.post.employee import CentHRSyncError, get_field_values

LOCK_TIMEOUT = 300
MIGRATE_MODULE_PREFIX = "centhr.api.migrate."

# exclude: links to local records that are not synced, so their names mean nothing on the target
# match_by_name: the record has the same name on every system
# submitted_only: drafts are not sent; the record goes to the target when it is submitted
# links: {fieldname: doctype}, sent with the target's name of the linked record (see RemoteLinks)
# dynamic_links: {fieldname: field that holds the doctype}
# tables: {table fieldname: {"exclude", "links", "dynamic_links"}} for the rows of a child table

# The IOU workflow, its approvers and the payment advice belong to this site. The entity site starts
# the record in its own first workflow state, and its submit moves it to the submitted state.
IOU_LOCAL_FIELDS = (
	"workflow_state",
	"line_manager",
	"current_approver",
	"proxy_approver",
	"hod_approved_by",
	"finance_1_approved_by",
	"finance_2_approved_by",
	"rejected_by",
	"pending_since",
	"escalated_at",
	"payment_advice",
)
ACCOUNTING_LINKS = {"cost_center": "Cost Center", "department": "Department"}

SYNC_CONFIG = {
	"Leave Allocation": {
		"exclude": ("compensatory_request", "leave_period", "leave_policy", "leave_policy_assignment"),
	},
	"Employee Checkin": {"exclude": ("attendance",)},
	"Shift Type": {"exclude": (), "match_by_name": True},
	"Employee Advance": {
		"submitted_only": True,
		# The entity site sets the paid, claimed and returned amounts from its own Payment Entries and
		# claims. Copied amounts would make its Payment Entry see the advance as paid already.
		"exclude": (
			*IOU_LOCAL_FIELDS,
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"pending_amount",
			"status",
		),
		"links": {"advance_account": "Account", **ACCOUNTING_LINKS},
	},
	"Expense Claim": {
		"submitted_only": True,
		# The entity site sets the reimbursed amount and status from its own Payment Entries
		"exclude": (
			*IOU_LOCAL_FIELDS,
			"expense_approver",
			"vehicle_log",
			"delivery_trip",
			"task",
			"total_amount_reimbursed",
			"status",
		),
		"links": {
			"payable_account": "Account",
			"bank_or_cash_account": "Account",
			"gain_loss_account": "Account",
			**ACCOUNTING_LINKS,
		},
		"tables": {
			"expenses": {"links": {"default_account": "Account", **ACCOUNTING_LINKS}},
			"taxes": {"links": {"account_head": "Account", **ACCOUNTING_LINKS}},
			"advances": {
				"links": {"employee_advance": "Employee Advance", "advance_account": "Account"},
				"dynamic_links": {"reference_name": "reference_type"},
			},
		},
	},
	"Payment Entry": {
		"submitted_only": True,
		# Bank Accounts, contacts and withholding entries are local records or made by the target's submit
		"exclude": (
			"status",
			"bank_account",
			"party_bank_account",
			"contact_person",
			"payment_order",
			"auto_repeat",
			"letter_head",
			"print_heading",
			"tax_withholding_entries",
		),
		"links": {"paid_from": "Account", "paid_to": "Account", "cost_center": "Cost Center"},
		"dynamic_links": {"party": "party_type"},
		"tables": {
			"references": {
				"exclude": ("payment_request",),
				"links": {"account": "Account"},
				"dynamic_links": {
					"reference_name": "reference_doctype",
					"advance_voucher_no": "advance_voucher_type",
				},
			},
			"taxes": {"links": {"account_head": "Account", "cost_center": "Cost Center"}},
			"deductions": {"links": {"account": "Account", "cost_center": "Cost Center"}},
		},
	},
}


def enqueue_job(method: str, doc, **kwargs) -> None:
	# Records migrated from the CentHR site must not be sent back to it
	if frappe.flags.centhr_migration or not get_targets(get_company(doc)):
		return

	frappe.enqueue(method, queue="short", enqueue_after_commit=True, **kwargs)


def is_unsent_draft(doc) -> bool:
	"""A draft of a submitted_only doctype. Its sync job is not needed.

	A draft that is on the target (migrated from it) is skipped as well: only a submit changes it there.
	"""
	return doc.docstatus == 0 and SYNC_CONFIG.get(doc.doctype, {}).get("submitted_only", False)


def sync_record(doctype: str, name: str) -> None:
	with sync_lock(doctype, name):
		if not frappe.db.exists(doctype, name):
			return

		doc = frappe.get_doc(doctype, name)
		ref = frappe._dict(doctype=doctype, name=name, label=get_label(doc))
		run_for_targets(ref, get_company(doc), lambda target: RecordSync(ref, target, doc).upsert())


def delete_record(doctype: str, name: str, company: str | None, label: str) -> None:
	# The local record is gone, so the job gets its company and label from the hook
	with sync_lock(doctype, name):
		ref = frappe._dict(doctype=doctype, name=name, label=label)
		run_for_targets(ref, company, lambda target: RecordSync(ref, target).delete())


class RecordSync:
	"""Syncs one local record to one target."""

	def __init__(self, ref, target, doc=None):
		self.ref = ref
		self.doc = doc
		self.config = SYNC_CONFIG[ref.doctype]
		self.client = TargetClient(target, ref)
		self.links = RemoteLinks(self)

	def upsert(self) -> None:
		doc = self.doc
		remote = self.find_remote(doc.name)

		if not remote:
			if doc.docstatus == 2:
				# cancelled before it ever reached the target
				return
			if doc.docstatus == 0 and self.config.get("submitted_only"):
				return
			self.client.insert(doc.doctype, self.build_payload())
			return

		if remote.docstatus == 1:
			payload = {"docstatus": 2} if doc.docstatus == 2 else self.get_update_after_submit_values()
			if not payload:
				return
		else:
			payload = self.build_payload()

		self.client.update(doc.doctype, remote.name, payload)

	def delete(self) -> None:
		remote = self.find_remote(self.ref.name)
		if not remote:
			return

		if remote.docstatus == 1:
			# the local cancel may not have reached the target yet
			self.client.update(self.ref.doctype, remote.name, {"docstatus": 2})

		self.client.delete(self.ref.doctype, remote.name)

	def build_payload(self) -> dict:
		doc = self.doc
		payload = get_field_values(doc)

		for fieldname in ("amended_from", *self.config["exclude"]):
			payload.pop(fieldname, None)

		if self.config.get("match_by_name"):
			payload["name"] = doc.name

		if doc.meta.is_submittable:
			payload["docstatus"] = doc.docstatus

		if doc.get("amended_from"):
			amended_from = self.find_remote(doc.amended_from)
			if amended_from:
				payload["amended_from"] = amended_from.name

		if doc.get("employee"):
			payload["employee"] = self.get_remote_employee(doc.employee)

		self.map_links(payload, self.config)
		for table, table_config in self.config.get("tables", {}).items():
			for row in payload.get(table) or ():
				for fieldname in table_config.get("exclude", ()):
					row.pop(fieldname, None)
				self.map_links(row, table_config)

		return frappe.parse_json(frappe.as_json(payload))

	def map_links(self, values: dict, config: dict) -> None:
		"""Replaces the local names in the link fields of `config` with the target's names."""
		for fieldname, doctype in config.get("links", {}).items():
			if values.get(fieldname):
				values[fieldname] = self.links.get(doctype, values[fieldname])

		for fieldname, doctype_field in config.get("dynamic_links", {}).items():
			if values.get(fieldname):
				values[fieldname] = self.links.get(values.get(doctype_field), values[fieldname])

	def get_update_after_submit_values(self) -> dict:
		# a submitted record on the target only accepts changes to "Allow on Submit" fields
		allowed = {df.fieldname for df in self.doc.meta.fields if df.allow_on_submit}
		return {key: value for key, value in self.build_payload().items() if key in allowed}

	def find_remote(self, name: str) -> frappe._dict | None:
		remote_name = name if self.config.get("match_by_name") else self.get_synced_name(name)
		if not remote_name:
			return None

		data = self.client.get_list(self.ref.doctype, [["name", "=", remote_name]], ["name", "docstatus"])
		return frappe._dict(data[0]) if data else None

	def get_synced_name(self, name: str, doctype: str | None = None) -> str | None:
		return self.get_pushed_name(name, doctype) or self.get_migrated_name(name, doctype)

	def get_pushed_name(self, name: str, doctype: str | None = None) -> str | None:
		doctype = doctype or self.ref.doctype
		return frappe.db.get_value(
			"CentHR API Logger",
			{
				"doctypes": doctype,
				"reference_name": name,
				"endpoint": self.client.url(doctype),
				"request_method": "POST",
				"status": "Success",
				"target_reference": ("is", "set"),
			},
			"target_reference",
			order_by="creation desc",
		)

	def get_migrated_name(self, name: str, doctype: str | None = None) -> str | None:
		# the migration tool logs the CentHR name as reference_name and the local name as target_reference
		return frappe.db.get_value(
			"CentHR API Logger",
			{
				"doctypes": doctype or self.ref.doctype,
				"target_reference": name,
				"company": self.client.target.company,
				"sync_method": ("like", f"{MIGRATE_MODULE_PREFIX}%"),
				"status": "Success",
			},
			"reference_name",
			order_by="creation desc",
		)

	def get_remote_employee(self, employee: str) -> str:
		# Employee sync sends employee_number (or the local ID) as the target's employee_number.
		# Employees migrated from the target keep its ID, which may have no employee_number there.
		employee_number = frappe.db.get_value("Employee", employee, "employee_number") or employee
		rows = self.client.get_list(
			"Employee",
			[],
			["name", "employee_number"],
			or_filters=[["employee_number", "=", employee_number], ["name", "=", employee_number]],
			limit=2,
		)
		by_number = [row for row in rows if row.get("employee_number") == employee_number]
		by_name = [row for row in rows if row["name"] == employee_number and not row.get("employee_number")]
		match = (by_number or by_name or [None])[0]
		if not match:
			self.client.fail(_("Employee {0} does not exist in the target system").format(employee))
		return match["name"]


def sync_lock(doctype: str, name: str):
	# one job per record at a time, so a quick insert + submit cannot POST the record twice
	return frappe.cache.lock(
		frappe.cache.make_key(f"centhr_sync::{doctype}::{name}"),
		timeout=LOCK_TIMEOUT,
		blocking_timeout=LOCK_TIMEOUT,
	)


def run_for_targets(ref, company: str | None, action, targets: list | None = None) -> None:
	"""Runs `action` for each target of the company, or for the given ones."""
	failed_targets = []

	for target in get_targets(company) if targets is None else targets:
		try:
			action(target)
		except CentHRSyncError:
			failed_targets.append(target.base_url)
		except Exception as e:
			TargetClient(target, ref).log("Failed", error=f"{type(e).__name__}: {e}")
			failed_targets.append(target.base_url)

	if failed_targets:
		notify_failure(ref, failed_targets)


def get_targets(company: str | None) -> list:
	"""Targets of the record's company. Records without a company go to every target once."""
	settings = frappe.get_cached_doc("CentHr Settings")
	if company:
		return [row for row in settings.authorization if row.company == company]

	targets = {}
	for row in settings.authorization:
		targets.setdefault((row.base_url.rstrip("/"), row.api_key), row)
	return list(targets.values())


def get_company(doc) -> str | None:
	if doc.get("company"):
		return doc.company
	if doc.get("employee"):
		return frappe.db.get_value("Employee", doc.employee, "company")
	return None


def get_label(doc) -> str:
	return doc.get("employee_name") or doc.name


def notify_failure(ref, failed_targets: list[str]) -> None:
	users = [row.user for row in frappe.get_cached_doc("CentHr Settings").error_alerts]
	if not users:
		return

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": ref.doctype,
			"document_name": ref.name,
			"subject": _("CentHR sync of {0} {1} failed for: {2}").format(
				_(ref.doctype), ref.name, ", ".join(failed_targets)
			),
		},
	)
