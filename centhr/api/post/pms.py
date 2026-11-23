# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

from centhr.api.common.pms_sync import enqueue_pms_job, sync_pms_record


def enqueue_pms_sync(doc, method=None):
	"""after_insert of every PMS DocType: send the new record to the company's site."""
	enqueue_pms_job("centhr.api.post.pms.sync_pms", doc, doctype=doc.doctype, name=doc.name)


def sync_pms(doctype: str, name: str) -> None:
	sync_pms_record(doctype, name)
