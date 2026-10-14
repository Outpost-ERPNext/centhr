# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_leave_allocation_sync(doc, method=None):
	enqueue_job("centhr.api.post.leave_allocation.sync_leave_allocation", doc, leave_allocation=doc.name)


def sync_leave_allocation(leave_allocation: str) -> None:
	sync_record("Leave Allocation", leave_allocation)
