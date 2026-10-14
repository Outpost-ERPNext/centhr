# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label


def enqueue_employee_checkin_delete(doc, method=None):
	enqueue_job(
		"centhr.api.delete.employee_checkin.delete_employee_checkin",
		doc,
		employee_checkin=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_employee_checkin(employee_checkin: str, company: str | None, label: str) -> None:
	delete_record("Employee Checkin", employee_checkin, company, label)
