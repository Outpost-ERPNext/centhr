# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record


def enqueue_employee_advance_update(doc, method=None):
	# on_update also runs on insert, which post/employee_advance.py handles
	if doc.flags.in_insert or is_unsent_draft(doc):
		return

	enqueue_job("centhr.api.update.employee_advance.update_employee_advance", doc, employee_advance=doc.name)


def update_employee_advance(employee_advance: str) -> None:
	# POSTs the record instead if it never reached the target, e.g. on its submit
	sync_record("Employee Advance", employee_advance)
