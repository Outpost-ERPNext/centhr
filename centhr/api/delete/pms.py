# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.common.pms_sync import delete_pms_record, enqueue_pms_job, get_pms_company
from centhr.api.post.employee import get_field_values


def enqueue_pms_delete(doc, method=None):
	"""on_trash of every PMS DocType. The record is found on the company's site by what it was
	about, so the job gets the values it had."""
	enqueue_pms_job(
		"centhr.api.delete.pms.delete_pms",
		doc,
		doctype=doc.doctype,
		name=doc.name,
		company=get_pms_company(doc),
		values=frappe.parse_json(frappe.as_json(get_field_values(doc))),
	)


def delete_pms(doctype: str, name: str, company: str | None, values: dict) -> None:
	delete_pms_record(doctype, name, company, values)
