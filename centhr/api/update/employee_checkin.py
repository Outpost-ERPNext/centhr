# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_employee_checkin_update(doc, method=None):
	# on_update also runs on insert, which post/employee_checkin.py handles
	if doc.flags.in_insert:
		return

	enqueue_job("centhr.api.update.employee_checkin.update_employee_checkin", doc, employee_checkin=doc.name)


def update_employee_checkin(employee_checkin: str) -> None:
	# POSTs the record instead if it never reached the target
	sync_record("Employee Checkin", employee_checkin)
