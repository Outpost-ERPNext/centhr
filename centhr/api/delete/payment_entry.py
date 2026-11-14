# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label
from centhr.api.post.payment_entry import is_iou_payment


def enqueue_payment_entry_delete(doc, method=None):
	if not is_iou_payment(doc):
		return

	enqueue_job(
		"centhr.api.delete.payment_entry.delete_payment_entry",
		doc,
		payment_entry=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_payment_entry(payment_entry: str, company: str | None, label: str) -> None:
	delete_record("Payment Entry", payment_entry, company, label)
