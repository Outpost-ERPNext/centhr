# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""What the PMS migrators share.

The PMS DocTypes of the CentHR site have no company field and name their records after that site's
employee IDs. Here every PMS record belongs to a company and is named after this site's employee ID,
so a migrated record gets a new name, and the records it points to (a KPI Result to its KPI Template,
a review to its allocation) are found again by what they are about: the employee and the period.
"""

import frappe
from frappe import _

from centhr.api.migrate.base import CHUNK_SIZE, SAVEPOINT, Migrator
from centhr.api.migrate.client import MigrationError

QUARTER_OF_MONTH = {
	month: f"Q{index // 3 + 1}"
	for index, month in enumerate(
		(
			"January",
			"February",
			"March",
			"April",
			"May",
			"June",
			"July",
			"August",
			"September",
			"October",
			"November",
			"December",
		)
	)
}


class PmsMigrator(Migrator):
	# The CentHR site's PMS DocTypes have no company; each company has its own site
	filter_by_company = False
	# Fields of duplicate_fields that hold an employee, matched through the employee map
	employee_fields: tuple[str, ...] = ("employee",)
	# Filters of the tool that are fields of the CentHR site's DocType
	remote_filter_fields: tuple[str, ...] = ()

	def get_section_filters(self, filters: frappe._dict) -> list:
		return [[field, "=", filters[field]] for field in self.remote_filter_fields if filters.get(field)]

	# Finding the record that is here already

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		if not self.duplicate_fields:
			# Found when it is migrated (find_existing); the list shows what the log says
			return {}
		for field in self.employee_fields:
			if field in self.duplicate_fields:
				self.employees.load([row.get(field) for row in rows])
		keys = {row["name"]: self.get_key(row) for row in rows}
		local_names = self.get_local_names([key for key in keys.values() if key])
		return {name: local_names.get(key) for name, key in keys.items() if key in local_names}

	def get_key(self, row: dict) -> tuple | None:
		key = []
		for fieldname in self.duplicate_fields:
			value = row.get(fieldname)
			if fieldname in self.employee_fields:
				value = self.employees.get_local(value)
				if not value:
					return None
			key.append(str(value or ""))
		return tuple(key)

	def get_local_names(self, keys: list[tuple]) -> dict[tuple, str]:
		first_values = list({key[0] for key in keys})
		filters = {"docstatus": ["!=", 2]} if self.meta.is_submittable else {}
		local_names = {}
		for start in range(0, len(first_values), CHUNK_SIZE):
			filters[self.duplicate_fields[0]] = ["in", first_values[start : start + CHUNK_SIZE]]
			for record in frappe.get_all(
				self.doctype, filters=filters, fields=["name", *self.duplicate_fields]
			):
				key = tuple(str(record[fieldname] or "") for fieldname in self.duplicate_fields)
				local_names[key] = record.name
		return local_names

	def find_existing(self, values: dict) -> str | None:
		return find_local(self.doctype, **{field: values.get(field) for field in self.duplicate_fields})

	# Creating it

	def create(self, values: dict):
		"""The record takes the name this site gives it, made of this site's employee ID."""
		frappe.db.savepoint(SAVEPOINT)
		try:
			doc = frappe.get_doc({"doctype": self.doctype, **values})
			self.before_insert(doc)
			doc.insert(ignore_permissions=True)
			if self.remote.get("docstatus") == 1:
				doc.submit()
			self.after_create(doc)
		except Exception:
			frappe.db.rollback(save_point=SAVEPOINT)
			raise
		return doc

	def before_insert(self, doc) -> None:
		pass

	def after_create(self, doc) -> None:
		pass

	# What a record is about

	def local_employee(self, remote_employee: str | None, label: str) -> str:
		employee = self.employees.get_local(remote_employee) if remote_employee else None
		if not employee:
			raise MigrationError(
				_("{0} {1} is not on this site. Migrate the employee first.").format(
					label, remote_employee or ""
				)
			)
		return employee

	def get_remote_questionnaire(self, name: str | None) -> frappe._dict:
		"""Employee, fiscal year and quarter of a questionnaire on the CentHR site."""
		if not name:
			raise MigrationError(_("It has no PMS Questionnaire, so its quarter is not known."))
		cache = self.__dict__.setdefault("_questionnaires", {})
		if name not in cache:
			remote = self.client.get_doc("PMS Questionnaire", name)
			cache[name] = frappe._dict(
				employee=remote.get("employee"),
				fiscal_year=remote.get("fiscal_year"),
				quarter=get_quarter(remote),
			)
		return cache[name]


def get_quarter(remote: dict) -> str:
	"""Older records of the CentHR site name a month instead of a quarter."""
	quarter = remote.get("quarter") or QUARTER_OF_MONTH.get(remote.get("month") or "")
	if not quarter:
		raise MigrationError(_("It has no quarter and no month, so its period is not known."))
	return quarter


def find_local(doctype: str, **about) -> str | None:
	"""The record here that is about the same thing; cancelled ones do not count."""
	filters = {field: value if value else ["is", "not set"] for field, value in about.items()}
	if frappe.get_meta(doctype).is_submittable:
		filters.setdefault("docstatus", ["!=", 2])
	return frappe.db.get_value(doctype, filters, "name")
