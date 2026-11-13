# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Syncs Department to the entity sites of its company, from the hooks in hooks.py.

ERPNext names a department "<department_name> - <company abbr>", and an entity site can use another
abbreviation for the same company. So the department on the target is found by department_name and
company, not by its name here. A department without a company goes once to every target.
"""

import frappe
from frappe import _

from centhr.api.common.record_sync import (
	RecordSync,
	enqueue_job,
	get_company,
	get_label,
	run_for_targets,
	sync_lock,
)
from centhr.api.common.target_client import TargetClient

DOCTYPE = "Department"
# Approvers, payroll cost center and leave block list link to records that are not synced
FIELDS = ("department_name", "parent_department", "company", "is_group", "disabled")


def enqueue_department_sync(doc, method=None):
	enqueue_job("centhr.api.department.sync_department", doc, department=doc.name)


def enqueue_department_update(doc, method=None):
	# on_update also runs on insert, which enqueue_department_sync handles
	if doc.flags.in_insert:
		return

	enqueue_job("centhr.api.department.sync_department", doc, department=doc.name)


def enqueue_department_delete(doc, method=None):
	# The local record is gone when the job runs, so it gets the values to find the target record here
	enqueue_job(
		"centhr.api.department.delete_department",
		doc,
		department=doc.name,
		company=get_company(doc),
		label=get_label(doc),
		match_values=get_match_values(doc),
	)


def sync_department(department: str) -> None:
	# POSTs the department when it is not on the target yet, PUTs it otherwise
	with sync_lock(DOCTYPE, department):
		if not frappe.db.exists(DOCTYPE, department):
			return

		doc = frappe.get_doc(DOCTYPE, department)
		ref = frappe._dict(doctype=DOCTYPE, name=department, label=get_label(doc))
		run_for_targets(ref, get_company(doc), lambda target: DepartmentSync(ref, target, doc).upsert())


def delete_department(department: str, company: str | None, label: str, match_values: dict) -> None:
	with sync_lock(DOCTYPE, department):
		ref = frappe._dict(doctype=DOCTYPE, name=department, label=label)
		run_for_targets(
			ref, company, lambda target: DepartmentSync(ref, target, match_values=match_values).delete()
		)


class DepartmentSync(RecordSync):
	"""Syncs one Department to one target, which can name it with another company abbreviation."""

	def __init__(self, ref, target, doc=None, match_values: dict | None = None):
		# RecordSync.__init__ reads SYNC_CONFIG, which has no Department entry
		self.ref = ref
		self.doc = doc
		self.config = {"exclude": ()}
		self.client = TargetClient(target, ref)
		self.match_values = match_values or get_match_values(doc)

	def find_remote(self, name: str) -> frappe._dict | None:
		# The POSTed name first, so a department whose department_name changed keeps its target record
		remote_name = self.get_pushed_name(name)
		filters = [["name", "=", remote_name]] if remote_name else to_filters(self.match_values)
		data = self.client.get_list(DOCTYPE, filters, ["name", "docstatus"])
		return frappe._dict(data[0]) if data else None

	def build_payload(self) -> dict:
		payload = {fieldname: self.doc.get(fieldname) for fieldname in FIELDS}
		payload["parent_department"] = self.get_remote_parent(self.doc.parent_department)
		return frappe.parse_json(frappe.as_json(payload))

	def get_remote_parent(self, parent: str | None) -> str | None:
		if not parent:
			return None

		values = frappe.db.get_value(DOCTYPE, parent, ["department_name", "company"], as_dict=True)
		# A department without a company, like "All Departments", has the same name everywhere
		if not values or not values.company:
			return parent

		data = self.client.get_list(DOCTYPE, to_filters(values), ["name"])
		if not data:
			self.client.fail(
				_("Parent Department {0} does not exist in the target system").format(parent)
			)
		return data[0]["name"]


def get_match_values(doc) -> dict:
	return {"department_name": doc.department_name, "company": doc.company or None}


def to_filters(values: dict) -> list:
	# A department without a company must match one without a company on the target
	return [
		[fieldname, "=", value] if value else [fieldname, "is", "not set"]
		for fieldname, value in values.items()
	]
