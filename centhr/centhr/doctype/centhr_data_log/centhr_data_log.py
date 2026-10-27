# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class CenthrDataLog(Document):
	"""One run of the Centhr Data Migration Tool, with one row for each selected record."""

	def add_record(self, name: str, result: frappe._dict, title: str | None = None) -> None:
		self.append(
			"records",
			{
				"reference_doctype": self.reference_doctype,
				"reference_name": name,
				"record_title": title or name,
				"status": result.status,
				"local_name": result.local_name,
				"posting_date": now_datetime(),
				"api_logger": result.log,
				"error": result.error,
			},
		)

	def set_summary(self, stopped: bool = False) -> None:
		statuses = [row.status for row in self.records]
		self.success_count = statuses.count("Success")
		self.already_exists_count = statuses.count("Already Exists")
		self.failed_count = statuses.count("Failed")

		if stopped:
			self.status = "Stopped"
		elif not self.failed_count:
			self.status = "Completed"
		elif self.failed_count == len(statuses):
			self.status = "Failed"
		else:
			self.status = "Partially Completed"
