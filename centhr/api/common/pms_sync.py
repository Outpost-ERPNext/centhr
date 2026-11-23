# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Sends PMS records to the company's site, one way.

PMS lives on this site. A company site that still has the PMS DocTypes of its own app gets a copy of
every record made, changed, cancelled or deleted here. Three things differ from the other synced
DocTypes (record_sync):

- The company site makes some records itself (a submitted KPI Template creates its KPI Result) and
  renames others, so a record is found there by what it is about, such as the employee and the month,
  and never by a logged name.
- Its DocTypes are older: they have no company, PMS Settings is one record for the site, and a few
  fields have other names.
- Saving a record there sends that site's own emails. So a target only gets PMS records when "Send
  PMS Records" is ticked on its row in CentHr Settings.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import cint

from centhr.api.common.record_sync import (
	RecordSync,
	get_label,
	get_targets,
	run_for_targets,
	sync_lock,
)
from centhr.api.common.remote_links import RemoteLinks
from centhr.api.common.target_client import TargetClient
from centhr.api.post.employee import get_field_values


@dataclass(frozen=True)
class Rows:
	"""The links in the rows of a child table."""

	employees: tuple[str, ...] = ()
	departments: tuple[str, ...] = ()


@dataclass(frozen=True)
class Shape(Rows):
	"""How a PMS DocType is sent to a company site."""

	# The fields, as they are sent, that say which record of the site this is
	key: tuple[str, ...] = ()
	# One record for the whole site, named after its DocType
	single: bool = False
	# Field -> the PMS DocType it links to; sent with the name that record has on the site
	links: dict[str, str] = field(default_factory=dict)
	# Field here -> its name on the site
	rename: dict[str, str] = field(default_factory=dict)
	# Fields that only mean something here
	exclude: tuple[str, ...] = ()
	tables: dict[str, Rows] = field(default_factory=dict)
	# Has the last word on what is sent: prepare(doc, payload)
	prepare: Callable | None = None


def send_weights_as_text(doc, payload: dict) -> None:
	"""The company site keeps a reviewer weight as text, and empty when that reviewer does not count."""
	for row in payload.get("departments") or []:
		for kind in ("superior", "peers"):
			row[f"{kind}_weight"] = str(cint(row.get(f"{kind}_weight"))) if cint(row.get(kind)) else ""


def send_outcome_as_pip(doc, payload: dict) -> None:
	"""The company site ticks PIP where this site names the outcome."""
	payload["pip"] = 1 if doc.outcome == "PIP" else 0


PERIOD = ("fiscal_year", "quarter")
SHAPES = {
	"KPI UOM": Shape(key=("name",)),
	"PMS Question Trait": Shape(key=("name",)),
	"PMS Question": Shape(key=("question", "department", "designation"), departments=("department",)),
	"PMS Settings": Shape(
		single=True,
		exclude=("company", "company_logo", "kpi_freeze_day", "grade_levels"),
		tables={"pms__channel": Rows(employees=("hrbps",))},
	),
	"PMS Employee Relationship": Shape(
		key=("employee",),
		employees=("employee", "line_manager"),
		departments=("department",),
		rename={"locked": "is_locked"},
		exclude=("company", "peer_names"),
		tables={"peers": Rows(employees=("employee",))},
	),
	"KPI Template": Shape(
		key=("employee", "fiscal_year", "month"),
		employees=("employee", "reviewer"),
		departments=("department",),
		exclude=("company",),
	),
	"KPI Result": Shape(
		key=("employee", "fiscal_year", "month"),
		employees=("employee",),
		departments=("department",),
		links={"kpi_template": "KPI Template"},
		exclude=("company",),
	),
	"PMS 360 Degree": Shape(
		key=PERIOD,
		exclude=("company",),
		tables={"departments": Rows(departments=("department",))},
		prepare=send_weights_as_text,
	),
	"PMS Questionnaire": Shape(
		key=("employee", *PERIOD),
		employees=("employee",),
		departments=("department",),
		exclude=("company",),
	),
	"PMS Form Allocation": Shape(
		key=("reviewer", "reviewee", *PERIOD),
		employees=("reviewer", "reviewee"),
		links={"form_reference": "PMS Questionnaire"},
		# The site shows an allocation as done from its review, not from a status of its own
		exclude=("company", "status", "review_date"),
	),
	"PMS Question Form": Shape(
		key=("pms_form_allocation",),
		employees=("reviewer", "reviewee"),
		departments=("department",),
		links={"pms_form_allocation": "PMS Form Allocation", "pms_questionnaire": "PMS Questionnaire"},
		exclude=("company", "quarter"),
	),
	"PMS Score Sheet": Shape(
		key=("employee", "pms_questionnaire"),
		employees=("employee",),
		departments=("department",),
		links={"pms_questionnaire": "PMS Questionnaire"},
		# Its approval there follows that site's own workflow
		exclude=("company", "status", "outcome", "kpi_score", "review_score", *PERIOD),
		prepare=send_outcome_as_pip,
	),
}


def enqueue_pms_job(method: str, doc, **kwargs) -> None:
	# Records migrated from the company site must not be sent back to it
	if frappe.flags.centhr_migration or not get_pms_targets(get_pms_company(doc)):
		return

	frappe.enqueue(method, queue="short", enqueue_after_commit=True, **kwargs)


def sync_pms_record(doctype: str, name: str) -> None:
	with sync_lock(doctype, name):
		if not frappe.db.exists(doctype, name):
			return

		doc = frappe.get_doc(doctype, name)
		company = get_pms_company(doc)
		run_for_targets(
			get_ref(doc), company, lambda target: PmsSync(target, doc).upsert(), get_pms_targets(company)
		)


def delete_pms_record(doctype: str, name: str, company: str | None, values: dict) -> None:
	"""The record is gone here, so the job gets the company and field values it had."""
	with sync_lock(doctype, name):
		doc = frappe.get_doc({"doctype": doctype, **values})
		doc.name = name
		run_for_targets(
			get_ref(doc), company, lambda target: PmsSync(target, doc).delete(), get_pms_targets(company)
		)


class NotOnSite(Exception):
	"""A record this one links to is not on the company site, and must not be sent now."""


class PmsSync(RecordSync):
	"""Sends one PMS record to one company site."""

	def __init__(self, target, doc):
		self.doc = doc
		# A delete only looks records up; it never sends one
		self.send_linked = True
		self.ref = get_ref(doc)
		self.shape = SHAPES[doc.doctype]
		# RecordSync's own options do not apply to PMS records
		self.config = {}
		self.client = TargetClient(target, self.ref)
		self.links = RemoteLinks(self)

	def upsert(self) -> None:
		doc, doctype = self.doc, self.doc.doctype
		payload = self.build_payload()
		remote = self.find(payload)

		if not remote:
			# A record cancelled before it reached the site has nothing to cancel there
			if doc.docstatus != 2:
				self.client.insert(doctype, payload)
		elif remote.docstatus == 1:
			# Submitted there: only a cancel still changes it
			if doc.docstatus == 2:
				self.client.update(doctype, remote.name, {"docstatus": 2})
		elif doc.docstatus != 2:
			self.client.update(doctype, remote.name, payload)

	def delete(self) -> None:
		if self.shape.single:
			return
		self.send_linked = False
		try:
			remote = self.find(self.build_payload())
		except NotOnSite:
			# What it belonged to never reached the site, so neither did it
			return
		if not remote:
			return

		if remote.docstatus == 1:
			# The cancel made here may not have reached the site yet
			self.client.update(self.doc.doctype, remote.name, {"docstatus": 2})
		self.client.delete(self.doc.doctype, remote.name)

	def find(self, payload: dict) -> frappe._dict | None:
		"""The site's record that is about the same thing; its cancelled ones do not count."""
		doctype = self.doc.doctype
		if self.shape.single:
			return frappe._dict(name=doctype, docstatus=0)

		filters = [
			[fieldname, "=", payload[fieldname]] if payload.get(fieldname) else [fieldname, "is", "not set"]
			for fieldname in self.shape.key
		]
		if self.doc.meta.is_submittable:
			filters.append(["docstatus", "!=", 2])
		rows = self.client.get_list(doctype, filters, ["name", "docstatus"])
		return frappe._dict(rows[0]) if rows else None

	def build_payload(self) -> dict:
		doc, shape = self.doc, self.shape
		payload = get_field_values(doc)
		payload["name"] = doc.name
		for fieldname in ("amended_from", *shape.exclude):
			payload.pop(fieldname, None)

		self.map_links(payload, shape)
		for table, rows in shape.tables.items():
			for row in payload.get(table) or []:
				self.map_links(row, rows)
		for fieldname, doctype in shape.links.items():
			if payload.get(fieldname):
				payload[fieldname] = self.get_remote_name(doctype, payload[fieldname])
		for fieldname, remote_fieldname in shape.rename.items():
			payload[remote_fieldname] = payload.pop(fieldname, None)

		if "name" not in shape.key:
			# The site names the record itself
			payload.pop("name")
		if doc.meta.is_submittable:
			payload["docstatus"] = doc.docstatus
		if shape.prepare:
			shape.prepare(doc, payload)
		return frappe.parse_json(frappe.as_json(payload))

	def map_links(self, values: dict, rows: Rows) -> None:
		"""Employees and departments are sent with the name they have on the site."""
		for doctype, fieldnames in (("Employee", rows.employees), ("Department", rows.departments)):
			for fieldname in fieldnames:
				if values.get(fieldname):
					values[fieldname] = self.links.get(doctype, values[fieldname])

	def get_remote_name(self, doctype: str, name: str) -> str:
		"""The name on the site of a PMS record this one links to. A record that is not there yet,
		such as the KPI Template of a new KPI Result, is sent first."""
		linked = PmsSync(self.client.target, frappe.get_doc(doctype, name))
		linked.send_linked = self.send_linked
		remote = linked.find(linked.build_payload())
		if not remote and not self.send_linked:
			raise NotOnSite
		if not remote:
			with sync_lock(doctype, name):
				linked.upsert()
			remote = linked.find(linked.build_payload())
		if not remote:
			self.client.fail(_("{0} {1} could not be sent to the target system").format(_(doctype), name))
		return remote.name


def get_pms_targets(company: str | None) -> list:
	"""The company's sites that take PMS records. A master without a company goes to all that do."""
	return [target for target in get_targets(company) if target.get("sync_pms")]


def get_pms_company(doc) -> str | None:
	"""The record's company: its own, its employee's, or its department's (a PMS Question)."""
	if doc.get("company"):
		return doc.company
	if doc.get("employee"):
		return frappe.db.get_value("Employee", doc.employee, "company")
	if doc.get("department"):
		return frappe.db.get_value("Department", doc.department, "company")
	return None


def get_ref(doc) -> frappe._dict:
	return frappe._dict(doctype=doc.doctype, name=doc.name, label=get_label(doc))
