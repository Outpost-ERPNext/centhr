# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.record_sync import delete_record, enqueue_job, get_company, get_label


def enqueue_shift_type_delete(doc, method=None):
	enqueue_job(
		"centhr.api.delete.shift_type.delete_shift_type",
		doc,
		shift_type=doc.name,
		company=get_company(doc),
		label=get_label(doc),
	)


def delete_shift_type(shift_type: str, company: str | None, label: str) -> None:
	delete_record("Shift Type", shift_type, company, label)
