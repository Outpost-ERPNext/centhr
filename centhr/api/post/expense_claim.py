# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import enqueue_job, is_unsent_draft, sync_record


def enqueue_expense_claim_sync(doc, method=None):
	if is_unsent_draft(doc):
		return

	enqueue_job("centhr.api.post.expense_claim.sync_expense_claim", doc, expense_claim=doc.name)


def sync_expense_claim(expense_claim: str) -> None:
	sync_record("Expense Claim", expense_claim)
