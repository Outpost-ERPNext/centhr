# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record
from centhr.api.post.payment_entry import is_iou_payment


def enqueue_payment_entry_update(doc, method=None):
	# on_update also runs on insert, which post/payment_entry.py handles
	if doc.flags.in_insert or is_unsent_draft(doc) or not is_iou_payment(doc):
		return

	enqueue_job("centhr.api.update.payment_entry.update_payment_entry", doc, payment_entry=doc.name)


def update_payment_entry(payment_entry: str) -> None:
	# POSTs the record instead if it never reached the target, e.g. on its submit
	sync_record("Payment Entry", payment_entry)
