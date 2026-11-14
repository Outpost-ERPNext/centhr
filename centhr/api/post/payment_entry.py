# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record

# Only payments of IOUs are synced: an Employee Advance paid out or an Expense Claim reimbursed
IOU_REFERENCE_DOCTYPES = {"Employee Advance", "Expense Claim"}


def is_iou_payment(doc) -> bool:
	reference_doctypes = {row.reference_doctype for row in doc.get("references") or ()}
	return (
		doc.party_type == "Employee"
		and bool(reference_doctypes)
		and reference_doctypes <= IOU_REFERENCE_DOCTYPES
	)


def enqueue_payment_entry_sync(doc, method=None):
	if is_unsent_draft(doc) or not is_iou_payment(doc):
		return

	enqueue_job("centhr.api.post.payment_entry.sync_payment_entry", doc, payment_entry=doc.name)


def sync_payment_entry(payment_entry: str) -> None:
	sync_record("Payment Entry", payment_entry)
