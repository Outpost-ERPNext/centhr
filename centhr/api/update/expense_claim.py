# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record


def enqueue_expense_claim_update(doc, method=None):
	# on_update also runs on insert, which post/expense_claim.py handles
	if doc.flags.in_insert or is_unsent_draft(doc):
		return

	enqueue_job("centhr.api.update.expense_claim.update_expense_claim", doc, expense_claim=doc.name)


def update_expense_claim(expense_claim: str) -> None:
	# POSTs the record instead if it never reached the target, e.g. on its submit
	sync_record("Expense Claim", expense_claim)
