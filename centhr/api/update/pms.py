# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.pms_sync import enqueue_pms_job, sync_pms_record


def enqueue_pms_update(doc, method=None):
	"""on_update, on_cancel and on_update_after_submit of every PMS DocType."""
	# on_update also runs on insert, which post/pms.py handles
	if doc.flags.in_insert:
		return

	enqueue_pms_job("centhr.api.update.pms.update_pms", doc, doctype=doc.doctype, name=doc.name)


def update_pms(doctype: str, name: str) -> None:
	# Sends the record as new if it never reached the company's site
	sync_pms_record(doctype, name)
