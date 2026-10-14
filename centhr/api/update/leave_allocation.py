# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_leave_allocation_update(doc, method=None):
	# on_update also runs on insert, which post/leave_allocation.py handles
	if doc.flags.in_insert:
		return

	enqueue_job("centhr.api.update.leave_allocation.update_leave_allocation", doc, leave_allocation=doc.name)


def update_leave_allocation(leave_allocation: str) -> None:
	# POSTs the record instead if it never reached the target
	sync_record("Leave Allocation", leave_allocation)
