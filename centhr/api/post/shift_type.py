# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, sync_record


def enqueue_shift_type_sync(doc, method=None):
	enqueue_job("centhr.api.post.shift_type.sync_shift_type", doc, shift_type=doc.name)


def sync_shift_type(shift_type: str) -> None:
	sync_record("Shift Type", shift_type)
