# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label


def enqueue_leave_allocation_delete(doc, method=None):
	enqueue_job(
		"centhr.api.delete.leave_allocation.delete_leave_allocation",
		doc,
		leave_allocation=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_leave_allocation(leave_allocation: str, company: str | None, label: str) -> None:
	delete_record("Leave Allocation", leave_allocation, company, label)
