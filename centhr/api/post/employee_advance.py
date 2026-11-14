# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record


def enqueue_employee_advance_sync(doc, method=None):
	if is_unsent_draft(doc):
		return

	enqueue_job("centhr.api.post.employee_advance.sync_employee_advance", doc, employee_advance=doc.name)


def sync_employee_advance(employee_advance: str) -> None:
	sync_record("Employee Advance", employee_advance)
