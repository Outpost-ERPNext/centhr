# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_employee_checkin_sync(doc, method=None):
	enqueue_job("centhr.api.post.employee_checkin.sync_employee_checkin", doc, employee_checkin=doc.name)


def sync_employee_checkin(employee_checkin: str) -> None:
	sync_record("Employee Checkin", employee_checkin)
