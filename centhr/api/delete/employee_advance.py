# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label


def enqueue_employee_advance_delete(doc, method=None):
	enqueue_job(
		"centhr.api.delete.employee_advance.delete_employee_advance",
		doc,
		employee_advance=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_employee_advance(employee_advance: str, company: str | None, label: str) -> None:
	delete_record("Employee Advance", employee_advance, company, label)
