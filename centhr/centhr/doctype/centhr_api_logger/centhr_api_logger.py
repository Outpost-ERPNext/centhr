# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import hashlib
import json

import frappe
from frappe import _
from frappe.model.document import Document

from centhr.centhr.doctype.centhr_api_logger.readable_error import get_readable_error

SYNC_MODULE_PREFIX = "centhr.api."
RESYNC_JOB = "centhr.centhr.doctype.centhr_api_logger.centhr_api_logger.run_resync"
MAX_RESYNC_ATTEMPTS = 3
REMOVAL_FIELDS = {
	"Attendance": ("employee", "employee_name", "attendance_date", "company", "docstatus"),
	"Leave Application": (
		"employee",
		"employee_name",
		"leave_type",
		"from_date",
		"to_date",
		"company",
		"docstatus",
	),
}


class CentHRAPILogger(Document):
	def onload(self):
		if self.status == "Failed" and not self.resynced:
			self.set_onload("resync_error", self.get_resync_error())

	def before_insert(self):
		self.set_sync_context()
		self.set_readable_error()

	def set_readable_error(self):
		"""Show a message the user can act on, and keep the raw error under Technical Details."""
		readable = get_readable_error(self)
		if readable and readable != self.error:
			self.error_details = self.error
			self.error = readable

	def set_sync_context(self):
		"""Record which sync job wrote this log, so that the same job can be run again on resync."""
		origin = frappe.flags.centhr_resync_of
		if origin:
			self.resynced_from = origin.name
			self.resync_count = origin.resync_count + 1
			self.sync_method = origin.sync_method
			self.sync_kwargs = origin.sync_kwargs
			return

		job = getattr(frappe.local, "job", None)
		if job and job.method.startswith(SYNC_MODULE_PREFIX):
			self.sync_method = job.method
			self.sync_kwargs = frappe.as_json(job.kwargs)

	@frappe.whitelist()
	def resync(self):
		self.check_permission("write")
		error = self.get_resync_error()
		if error:
			frappe.throw(error, title=_("Cannot Resync"))

		if not self.sync_method:
			self.set_inferred_sync_job()
		self.db_set(
			{"sync_method": self.sync_method, "sync_kwargs": self.sync_kwargs}, update_modified=False
		)
		self.mark_resynced()
		frappe.enqueue(
			RESYNC_JOB,
			queue="short",
			job_id=f"centhr_resync::{self.get_job_key()}",
			deduplicate=True,
			enqueue_after_commit=True,
			log=self.name,
		)

	def get_resync_error(self) -> str | None:
		if self.status != "Failed":
			return _("Only failed logs can be resynced")
		if self.resynced:
			return _("This log has already been resynced")
		if self.resync_count >= MAX_RESYNC_ATTEMPTS:
			return _("Resync limit of {0} attempts reached").format(MAX_RESYNC_ATTEMPTS)

		if self.sync_method or self.get_inferred_sync_job()[0]:
			return None

		if self.doctypes and self.reference_name and not frappe.db.exists(self.doctypes, self.reference_name):
			return _("{0} {1} no longer exists, so there is nothing to resync").format(
				self.doctypes, self.reference_name
			)
		return _(
			"Cannot work out the sync job for this log from the current state of {0} {1}. "
			"Save, submit or cancel it again to sync it"
		).format(self.doctypes, self.reference_name)

	def set_inferred_sync_job(self):
		"""Work out the sync job for logs written before the job was recorded on each log."""
		method, kwargs = self.get_inferred_sync_job()
		if method:
			self.sync_method = method
			self.sync_kwargs = frappe.as_json(kwargs)

	def get_inferred_sync_job(self) -> tuple[str | None, dict | None]:
		if self.doctypes not in ("Employee", *REMOVAL_FIELDS) or not self.reference_name:
			return None, None

		# DELETE only ever came from a removal job, POST/PUT only from a create/update job.
		# Lookup (GET) failures could be either, so the document's current state decides,
		# except the linked-records check, which only the employee delete job makes.
		allow_write = self.request_method != "DELETE" and "linked_with" not in (self.endpoint or "")
		allow_removal = self.request_method not in ("POST", "PUT")
		docstatus = frappe.db.get_value(self.doctypes, self.reference_name, "docstatus")

		if self.doctypes == "Employee":
			if docstatus is None:
				return self.get_employee_delete_job() if allow_removal else (None, None)
			if not allow_write:
				return None, None
			if self.request_method == "PUT":
				return "centhr.api.update.employee.update_employee", {"employee": self.reference_name}
			return "centhr.api.post.employee.sync_employee", {"employee": self.reference_name}

		module = frappe.scrub(self.doctypes)
		if docstatus == 1 and allow_write:
			return f"centhr.api.post.{module}.sync_{module}", {module: self.reference_name}
		if docstatus == 2 and allow_removal:
			return f"centhr.api.delete.{module}.sync_{module}_removal", {
				"action": "cancel",
				module: self.get_removal_snapshot(),
			}
		return None, None

	def get_employee_delete_job(self) -> tuple[str, dict]:
		return "centhr.api.delete.employee.delete_employee", {
			"employee": self.reference_name,
			"employee_name": self.name1,
			"employee_number": self.reference_name,
			"company": self.company,
		}

	def get_removal_snapshot(self) -> dict:
		values = frappe.db.get_value(
			self.doctypes, self.reference_name, REMOVAL_FIELDS[self.doctypes], as_dict=True
		)
		return {"name": self.reference_name, **frappe.parse_json(frappe.as_json(values))}

	def get_job_key(self) -> str:
		return hashlib.md5(f"{self.sync_method}:{self.sync_kwargs}".encode()).hexdigest()

	def mark_resynced(self):
		"""Mark this log and every other pending failure of the same sync job, so each failure is resynced once."""
		frappe.db.set_value(
			"CentHR API Logger",
			{
				"status": "Failed",
				"resynced": 0,
				"sync_method": self.sync_method,
				"sync_kwargs": self.sync_kwargs,
			},
			"resynced",
			1,
		)
		# Older failures of the same document have no job recorded; this resync covers them too.
		frappe.db.set_value(
			"CentHR API Logger",
			{
				"status": "Failed",
				"resynced": 0,
				"sync_method": ("is", "not set"),
				"doctypes": self.doctypes,
				"reference_name": self.reference_name,
				"request_method": self.request_method or ("is", "not set"),
			},
			"resynced",
			1,
		)
		self.resynced = 1


@frappe.whitelist()
def resync_logs(names: str | list) -> int:
	names = frappe.parse_json(names) if isinstance(names, str) else names
	count = 0

	for name in names:
		log = frappe.get_doc("CentHR API Logger", name)
		# Failures of the same job are marked when the first one is resynced.
		if log.get_resync_error():
			continue

		log.resync()
		count += 1

	return count


def run_resync(log: str) -> None:
	origin = frappe.get_doc("CentHR API Logger", log)
	frappe.flags.centhr_resync_of = origin

	try:
		frappe.get_attr(origin.sync_method)(**json.loads(origin.sync_kwargs))
	except Exception as e:
		insert_resync_failure(origin, f"{type(e).__name__}: {e}")
	finally:
		frappe.flags.centhr_resync_of = None


def insert_resync_failure(origin, error: str) -> None:
	frappe.get_doc(
		{
			"doctype": "CentHR API Logger",
			"doctypes": origin.doctypes,
			"reference_name": origin.reference_name,
			"name1": origin.name1,
			"company": origin.company,
			"status": "Failed",
			"error": error,
		}
	).insert(ignore_permissions=True)
