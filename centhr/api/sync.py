# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Create, update and delete HR records on the target systems configured in CentHr Settings.

Every save of a synced doctype enqueues `sync_to_targets`, which POSTs the record the first
time and PUTs it afterwards (including submit and cancel). Deleting the record enqueues
`delete_from_targets`. The target-side name of a record is taken from its successful POST
in CentHR API Logger, except for doctypes named by hand (Shift Type), which keep their name.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification

from centhr.api.post.employee import CentHRSyncError, get_field_values
from centhr.api.target_client import TargetClient

LOCK_TIMEOUT = 300

# exclude: links to local records that are not synced, so their names mean nothing on the target
# match_by_name: the record has the same name on every system
SYNC_CONFIG = {
	"Leave Allocation": {
		"exclude": ("compensatory_request", "leave_period", "leave_policy", "leave_policy_assignment"),
	},
	"Employee Checkin": {"exclude": ("attendance",)},
	"Shift Type": {"exclude": (), "match_by_name": True},
}


def enqueue_sync(doc, method=None):
	# Records migrated from the CentHR site must not be sent back to it
	if frappe.flags.centhr_migration or not get_targets(get_company(doc)):
		return

	frappe.enqueue(
		"centhr.api.sync.sync_to_targets",
		queue="short",
		enqueue_after_commit=True,
		doctype=doc.doctype,
		name=doc.name,
	)


def enqueue_delete(doc, method=None):
	company = get_company(doc)
	if frappe.flags.centhr_migration or not get_targets(company):
		return

	frappe.enqueue(
		"centhr.api.sync.delete_from_targets",
		queue="short",
		enqueue_after_commit=True,
		doctype=doc.doctype,
		name=doc.name,
		company=company,
		label=get_label(doc),
	)


def sync_to_targets(doctype: str, name: str) -> None:
	with sync_lock(doctype, name):
		if not frappe.db.exists(doctype, name):
			return

		doc = frappe.get_doc(doctype, name)
		ref = frappe._dict(doctype=doctype, name=name, label=get_label(doc))
		run_for_targets(ref, get_company(doc), lambda target: RecordSync(ref, target, doc).upsert())


def delete_from_targets(doctype: str, name: str, company: str | None, label: str) -> None:
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

	def upsert(self) -> None:
		doc = self.doc
		remote = self.find_remote(doc.name)

		if not remote:
			if doc.docstatus == 2:
				# cancelled before it ever reached the target
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

		return frappe.parse_json(frappe.as_json(payload))

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

	def get_synced_name(self, name: str) -> str | None:
		return frappe.db.get_value(
			"CentHR API Logger",
			{
				"doctypes": self.ref.doctype,
				"reference_name": name,
				"endpoint": self.client.url(self.ref.doctype),
				"request_method": "POST",
				"status": "Success",
				"target_reference": ("is", "set"),
			},
			"target_reference",
			order_by="creation desc",
		)

	def get_remote_employee(self, employee: str) -> str:
		# Employee sync sends employee_number (or the local ID) as the target's employee_number
		employee_number = frappe.db.get_value("Employee", employee, "employee_number") or employee
		data = self.client.get_list("Employee", [["employee_number", "=", employee_number]], ["name"])
		if not data:
			self.client.fail(_("Employee {0} does not exist in the target system").format(employee))
		return data[0]["name"]


def sync_lock(doctype: str, name: str):
	# one job per record at a time, so a quick insert + submit cannot POST the record twice
	return frappe.cache.lock(
		frappe.cache.make_key(f"centhr_sync::{doctype}::{name}"),
		timeout=LOCK_TIMEOUT,
		blocking_timeout=LOCK_TIMEOUT,
	)


def run_for_targets(ref, company: str | None, action) -> None:
	failed_targets = []

	for target in get_targets(company):
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
