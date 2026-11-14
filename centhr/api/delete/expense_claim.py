# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label


def enqueue_expense_claim_delete(doc, method=None):
	enqueue_job(
		"centhr.api.delete.expense_claim.delete_expense_claim",
		doc,
		expense_claim=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_expense_claim(expense_claim: str, company: str | None, label: str) -> None:
	delete_record("Expense Claim", expense_claim, company, label)
