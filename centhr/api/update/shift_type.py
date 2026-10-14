# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_shift_type_update(doc, method=None):
	# on_update also runs on insert, which post/shift_type.py handles
	if doc.flags.in_insert:
		return

	enqueue_job("centhr.api.update.shift_type.update_shift_type", doc, shift_type=doc.name)


def update_shift_type(shift_type: str) -> None:
	# POSTs the record instead if it never reached the target
	sync_record("Shift Type", shift_type)
