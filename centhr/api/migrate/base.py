# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Copy records from a company's CentHR site into this site.

A Migrator lists the records of one DocType on the CentHR site (fetch) and creates selected ones
here (migrate). Each migrated record writes one CentHR API Logger entry, whose Resync runs the
module-level `migrate(company, name)` of the subclass again for that record only.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, getdate, strip_html

from centhr.api.migrate.client import RESPONSE_LOG_LIMIT, MigrationError, TargetClient
from centhr.api.migrate.employee_map import EmployeeMap
from centhr.api.migrate.tree_map import NAME_FIELDS, TreeMap

LOGGER = "CentHR API Logger"
CHUNK_SIZE = 1000
SAVEPOINT = "centhr_migration"
# Set by the CentHR site for its own records, or renumbered here
SYSTEM_FIELDS = {
	"name",
	"owner",
	"creation",
	"modified",
	"modified_by",
	"docstatus",
	"idx",
	"doctype",
	"parent",
	"parentfield",
	"parenttype",
	"naming_series",
	"amended_from",
	"_user_tags",
	"_comments",
	"_assign",
	"_liked_by",
	"_seen",
}
# Files live on the CentHR site, so their URLs do not work here
ATTACH_FIELDTYPES = ("Attach", "Attach Image")


class Migrator:
	doctype: str
	# Columns that the tool shows, read from the CentHR site
	list_fields: tuple[str, ...]
	# Fields that identify the same record on this site
	duplicate_fields: tuple[str, ...]
	# Links to records that get a new name here (naming series), so the old value would be wrong
	cleared_fields: tuple[str, ...] = ()
	title_field = "employee_name"
	filter_by_company = True
	order_by = "name asc"

	def __init__(self, company: str):
		self.company = company
		self.client = TargetClient(company)
		self.employees = EmployeeMap(self.client)
		self.tree_map = TreeMap(self.client, company)
		self.meta = frappe.get_meta(self.doctype)
		self.remote = {}
		self.notes = []

	@classmethod
	def get_sync_method(cls) -> str:
		return f"{cls.__module__}.migrate"

	def fetch(self, filters: dict) -> list[dict]:
		filters = frappe._dict(filters or {})
		validate_date_range(filters)

		remote_filters = self.get_remote_filters(filters)
		if remote_filters is None:
			return []

		rows = self.client.get_all(
			self.doctype, remote_filters, list({"name", *self.list_fields}), order_by=self.order_by
		)
		self.set_status(rows)
		return rows

	def migrate(self, name: str) -> frappe._dict:
		frappe.flags.centhr_migration = True
		self.remote, self.notes = {}, []

		try:
			result = self.migrate_record(name)
		except MigrationError as e:
			result = frappe._dict(status="Failed", error=str(e), log_fields=e.log_fields)
		except Exception as e:
			result = frappe._dict(status="Failed", error=get_error_message(e))
		finally:
			frappe.flags.centhr_migration = False
			frappe.clear_messages()

		result.log = self.insert_log(name, result)
		return result

	# Fetch

	def get_remote_filters(self, filters: frappe._dict) -> list | None:
		"""Filters for the CentHR site. None means that nothing can match."""
		remote = []
		if self.filter_by_company:
			remote.append(["company", "=", self.company])
		if self.meta.is_submittable:
			remote.append(["docstatus", "!=", 2])

		if filters.employee:
			employee = self.employees.get_remote(filters.employee)
			if not employee:
				return None
			remote.append(["employee", "=", employee])

		return remote + self.get_section_filters(filters)

	def get_section_filters(self, filters: frappe._dict) -> list:
		return []

	def set_status(self, rows: list[dict]) -> None:
		existing = self.get_existing_names(rows)
		logs, created = self.get_logs([row["name"] for row in rows])

		for row in rows:
			log = logs.get(row["name"], {})
			local_name = existing.get(row["name"])
			if local_name:
				status = "Success" if created.get(row["name"]) == local_name else "Already Exists"
			else:
				status = log.get("status") or "Pending"

			row.update(
				migration_status=status,
				local_name=local_name,
				error=log.get("error") if status == "Failed" else None,
				log=log.get("name"),
			)

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		"""Map each CentHR record to the matching record on this site."""
		if "employee" in self.duplicate_fields:
			self.employees.load([row.get("employee") for row in rows])

		keys = {row["name"]: self.get_key(row) for row in rows}
		local_names = self.get_local_names([key for key in keys.values() if key])
		return {name: local_names.get(key) for name, key in keys.items() if key in local_names}

	def get_key(self, row: dict) -> tuple | None:
		key = []
		for fieldname in self.duplicate_fields:
			value = row.get(fieldname)
			if fieldname == "employee":
				value = self.employees.get_local(value)
			if not value:
				return None
			key.append(str(value))
		return tuple(key)

	def get_local_names(self, keys: list[tuple]) -> dict[tuple, str]:
		first_values = list({key[0] for key in keys})
		filters = {"docstatus": ["!=", 2]} if self.meta.is_submittable else {}
		local_names = {}

		for start in range(0, len(first_values), CHUNK_SIZE):
			filters[self.duplicate_fields[0]] = ["in", first_values[start : start + CHUNK_SIZE]]
			records = frappe.get_all(self.doctype, filters=filters, fields=["name", *self.duplicate_fields])
			for record in records:
				key = tuple(str(record[fieldname]) for fieldname in self.duplicate_fields)
				local_names[key] = record.name

		return local_names

	def get_logs(self, names: list[str]) -> tuple[dict[str, dict], dict[str, str]]:
		"""Return the latest log of each record, and the record that this tool created for it."""
		logs, created = {}, {}
		for start in range(0, len(names), CHUNK_SIZE):
			for log in frappe.get_all(
				LOGGER,
				filters={
					"doctypes": self.doctype,
					"company": self.company,
					"sync_method": self.get_sync_method(),
					"reference_name": ["in", names[start : start + CHUNK_SIZE]],
				},
				fields=["name", "reference_name", "status", "error", "target_reference"],
				order_by="creation asc",
			):
				logs[log.reference_name] = log
				if log.status == "Success" and log.target_reference:
					created[log.reference_name] = log.target_reference
		return logs, created

	# Migrate

	def migrate_record(self, name: str) -> frappe._dict:
		self.remote = self.client.get_doc(self.doctype, name)
		values = self.prepare(self.remote)

		existing = self.find_existing(values)
		if existing:
			self.notes.insert(0, _("Already exists on this site as {0}").format(existing))
			return frappe._dict(status="Already Exists", local_name=existing)

		doc = self.create(values)
		return frappe._dict(status="Success", local_name=doc.name)

	def prepare(self, remote: dict) -> dict:
		values = self.strip(remote, self.meta, self.cleared_fields)
		self.map_links(self.meta, values)

		for df in self.meta.get_table_fields():
			child_meta = frappe.get_meta(df.options)
			values[df.fieldname] = [self.strip(row, child_meta) for row in values.get(df.fieldname) or []]
			for row in values[df.fieldname]:
				self.map_links(child_meta, row)

		return values

	def strip(self, record: dict, meta, cleared_fields: tuple = ()) -> dict:
		skipped = SYSTEM_FIELDS.union(cleared_fields)
		skipped.update(df.fieldname for df in meta.fields if df.fieldtype in ATTACH_FIELDTYPES)
		return {key: value for key, value in record.items() if key not in skipped}

	def map_links(self, meta, values: dict) -> None:
		"""Point each Link to the record of this site. Clear optional links that do not exist here."""
		for df in meta.get_link_fields():
			value = values.get(df.fieldname)
			if not value:
				continue

			local = self.get_local_link(df.options, value)
			if local:
				values[df.fieldname] = local
			elif df.reqd:
				raise MigrationError(
					_("{0} {1} does not exist on this site. Migrate or create it first.").format(
						_(df.options), value
					)
				)
			else:
				values[df.fieldname] = None
				self.notes.append(_("{0} {1} not found, left empty").format(_(df.label), value))

	def get_local_link(self, doctype: str, value: str) -> str | None:
		if doctype == "Employee":
			return self.employees.get_local(value)
		if doctype in NAME_FIELDS:
			return self.tree_map.get_local(doctype, value)
		# Names match without regard to case, so take the exact name used on this site
		return frappe.db.get_value(doctype, value, "name")

	def find_existing(self, values: dict) -> str | None:
		filters = {fieldname: values.get(fieldname) for fieldname in self.duplicate_fields}
		if self.meta.is_submittable:
			filters["docstatus"] = ["!=", 2]
		return frappe.db.get_value(self.doctype, filters, "name")

	def create(self, values: dict):
		# Keep the name of the CentHR site, so the record has the same ID on both sites
		name = self.remote["name"]
		if frappe.db.exists(self.doctype, name):
			raise MigrationError(
				_("{0} {1} already exists on this site as a different record").format(_(self.doctype), name)
			)

		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values})
			doc.insert(ignore_permissions=True, set_name=name)
			self.update_series(name)
			if self.remote.get("docstatus") == 1:
				doc.submit()
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise
		return doc

	def update_series(self, name: str) -> None:
		"""Move the naming series counter past the copied name, so new records here do not take it."""
		series = self.remote.get("naming_series")
		# Amended names add a suffix to a name that the series counted already
		if not series or self.remote.get("amended_from") or not series.rstrip(".").endswith("#"):
			return

		digits = len(re.findall(r"#+", series)[-1])
		prefix, count = name[:-digits], name[-digits:]
		if not count.isdigit():
			return

		Series = frappe.qb.DocType("Series")
		current = frappe.db.get_value("Series", prefix, "current", order_by="name", for_update=True)
		if current is None:
			frappe.qb.into(Series).insert(prefix, cint(count)).columns("name", "current").run()
		elif cint(current) < cint(count):
			frappe.qb.update(Series).set(Series.current, cint(count)).where(Series.name == prefix).run()

	def insert_log(self, name: str, result: frappe._dict) -> str:
		log_fields = result.log_fields or {
			"request_method": "GET",
			"endpoint": self.client.get_url(self.doctype, name),
			"api_response": frappe.as_json(self.remote)[:RESPONSE_LOG_LIMIT],
		}
		log = frappe.get_doc(
			{
				"doctype": LOGGER,
				"doctypes": self.doctype,
				"reference_name": name,
				"name1": self.remote.get(self.title_field) or name,
				"company": self.company,
				"status": "Failed" if result.status == "Failed" else "Success",
				# Only records created here; fetch reads this to tell Success from Already Exists
				"target_reference": result.local_name if result.status == "Success" else None,
				"error": result.error or "; ".join(self.notes) or None,
				"sync_method": self.get_sync_method(),
				"sync_kwargs": frappe.as_json({"company": self.company, "name": name}),
				**log_fields,
			}
		).insert(ignore_permissions=True)
		return log.name


def validate_date_range(filters: frappe._dict) -> None:
	if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date"), title=_("Invalid Date Range"))


def get_error_message(e: Exception) -> str:
	return strip_html(str(e)).strip() or type(e).__name__


def get_overlap_filters(filters: frappe._dict, from_field: str, to_field: str) -> list:
	"""Records whose period overlaps the selected date range."""
	remote = []
	if filters.from_date:
		remote.append([to_field, ">=", filters.from_date])
	if filters.to_date:
		remote.append([from_field, "<=", filters.to_date])
	return remote
