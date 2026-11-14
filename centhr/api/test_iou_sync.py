# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

from unittest.mock import patch
from urllib.parse import unquote

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.common.record_sync import RecordSync, is_unsent_draft
from centhr.api.common.target_client import TargetClient
from centhr.api.post.employee import CentHRSyncError
from centhr.api.post.payment_entry import enqueue_payment_entry_sync, is_iou_payment

# The entity site names the company's accounts with another abbreviation than this site
REMOTE_ABBR = "_RMT"
REMOTE_EMPLOYEE = "HR-EMP-REMOTE-1"
EMPLOYEE_NUMBER = "_T-IOU-SYNC-1"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


class FakeSite:
	"""Answers GET with the `remote` records of the URL's doctype that match the filters, and records
	every request. POST and PUT answer with `name`."""

	def __init__(self, remote: dict[str, list[dict]]):
		self.remote = remote
		self.calls = []

	def __call__(self, method, url, **kwargs):
		self.calls.append(frappe._dict(method=method, url=url, json=kwargs.get("json")))
		if method == "GET":
			doctype = unquote(url.rsplit("/api/resource/", 1)[1])
			params = kwargs["params"]
			rows = self.remote.get(doctype, [])
			rows = [row for row in rows if all(matches(row, f) for f in frappe.parse_json(params["filters"]))]
			if params.get("or_filters"):
				or_filters = frappe.parse_json(params["or_filters"])
				rows = [row for row in rows if any(matches(row, f) for f in or_filters)]
			return [{"docstatus": 0, **row} for row in rows]
		if method in ("POST", "PUT"):
			return {"name": "REMOTE-NEW"}
		return None

	def writes(self):
		return [call for call in self.calls if call.method != "GET"]


def matches(row: dict, condition: list) -> bool:
	field, operator, value = condition
	if operator == "in":
		return row.get(field) in value
	return row.get(field) == value


# The tests mock the entity site and build the documents in memory, so no records are saved
class IntegrationTestIOUSync(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", limit=1)[0]
		cls.abbr = frappe.get_cached_value("Company", cls.company, "abbr")
		cls.account = frappe.db.get_value(
			"Account",
			{"company": cls.company, "is_group": 0, "name": ["like", f"% - {cls.abbr}"]},
			["name", "account_name"],
			as_dict=True,
		)
		cls.remote_account = f"{cls.account.name.removesuffix(' - ' + cls.abbr)} - {REMOTE_ABBR}"

	def setUp(self):
		self.target = FakeTarget(company=self.company, base_url="http://entity.test/", api_key="key")
		# The logged POSTs of one test must not tell the next one that a record is on the target
		frappe.db.savepoint("iou_sync_test")
		self.addCleanup(frappe.db.rollback, save_point="iou_sync_test")

	def remote(self, **extra) -> dict:
		return {
			"Company": [{"name": self.company, "abbr": REMOTE_ABBR}],
			"Employee": [{"name": REMOTE_EMPLOYEE, "employee_number": EMPLOYEE_NUMBER}],
			"Account": [{"name": self.remote_account, "account_name": self.account.account_name}],
			**extra,
		}

	def make_advance(self, docstatus=1, **values):
		doc = frappe.new_doc("Employee Advance")
		doc.update(
			{
				"name": "_T-IOU-ADV-1",
				"employee": EMPLOYEE_NUMBER,
				"company": self.company,
				"posting_date": "2026-11-01",
				"advance_amount": 1000,
				"paid_amount": 1000,
				"advance_account": self.account.name,
				"workflow_state": "Approved",
				"current_approver": "Administrator",
				**values,
			}
		)
		doc.docstatus = docstatus
		return doc

	def make_claim(self):
		doc = frappe.new_doc("Expense Claim")
		doc.update(
			{
				"name": "_T-IOU-CLM-1",
				"employee": EMPLOYEE_NUMBER,
				"company": self.company,
				"payable_account": self.account.name,
				"expense_approver": "Administrator",
				"approval_status": "Approved",
				"total_amount_reimbursed": 500,
			}
		)
		doc.append(
			"expenses", {"amount": 500, "sanctioned_amount": 500, "default_account": self.account.name}
		)
		doc.append(
			"advances",
			{
				"employee_advance": "_T-IOU-ADV-1",
				"advance_account": self.account.name,
				"allocated_amount": 500,
			},
		)
		doc.docstatus = 1
		return doc

	def make_payment(self, party_type="Employee", reference_doctype="Employee Advance"):
		doc = frappe.new_doc("Payment Entry")
		doc.update(
			{
				"name": "_T-IOU-PE-1",
				"company": self.company,
				"payment_type": "Pay",
				"party_type": party_type,
				"party": EMPLOYEE_NUMBER,
				"paid_from": self.account.name,
				"paid_to": self.account.name,
				"paid_amount": 1000,
				"bank_account": "_Test Local Bank Account",
			}
		)
		doc.append(
			"references",
			{
				"reference_doctype": reference_doctype,
				"reference_name": "_T-IOU-ADV-1",
				"allocated_amount": 1000,
			},
		)
		doc.docstatus = 1
		return doc

	def log_pushed(self, doctype: str, name: str, remote_name: str):
		"""The successful POST that RecordSync takes the target's name from."""
		frappe.get_doc(
			{
				"doctype": "CentHR API Logger",
				"doctypes": doctype,
				"reference_name": name,
				"company": self.company,
				"endpoint": TargetClient(self.target, frappe._dict(doctype=doctype)).url(doctype),
				"request_method": "POST",
				"status": "Success",
				"target_reference": remote_name,
			}
		).insert(ignore_permissions=True)

	def upsert(self, doc, site: FakeSite):
		ref = frappe._dict(doctype=doc.doctype, name=doc.name, label=doc.name)
		with patch.object(TargetClient, "request", side_effect=site):
			RecordSync(ref, self.target, doc).upsert()

	def test_draft_advance_is_not_sent(self):
		doc = self.make_advance(docstatus=0)
		self.assertTrue(is_unsent_draft(doc))

		site = FakeSite(self.remote())
		self.upsert(doc, site)
		self.assertEqual(site.writes(), [])

	def test_submitted_advance_is_posted_with_target_names(self):
		site = FakeSite(self.remote())
		self.upsert(self.make_advance(), site)

		[post] = site.writes()
		self.assertEqual(post.method, "POST")
		self.assertEqual(post.json["advance_account"], self.remote_account)
		self.assertEqual(post.json["employee"], REMOTE_EMPLOYEE)
		self.assertEqual(post.json["docstatus"], 1)
		# The entity site sets these itself
		for fieldname in ("workflow_state", "current_approver", "paid_amount", "status"):
			self.assertNotIn(fieldname, post.json)

	def test_account_is_found_by_account_name(self):
		renamed = f"9999 - {self.account.account_name} - XYZ"
		site = FakeSite(
			self.remote(
				Account=[
					{"name": renamed, "account_name": self.account.account_name, "company": self.company}
				]
			)
		)
		self.upsert(self.make_advance(), site)

		[post] = site.writes()
		self.assertEqual(post.json["advance_account"], renamed)

	def test_missing_account_fails_without_a_write(self):
		site = FakeSite(self.remote(Account=[]))
		with self.assertRaises(CentHRSyncError):
			self.upsert(self.make_advance(), site)

		self.assertEqual(site.writes(), [])
		log = frappe.get_last_doc("CentHR API Logger", {"reference_name": "_T-IOU-ADV-1"})
		self.assertEqual(log.status, "Failed")
		self.assertIn(self.account.name, log.error)

	def test_claim_uses_the_remote_advance(self):
		self.log_pushed("Employee Advance", "_T-IOU-ADV-1", "REMOTE-ADV-9")
		site = FakeSite(self.remote())
		self.upsert(self.make_claim(), site)

		[post] = site.writes()
		[advance] = post.json["advances"]
		self.assertEqual(advance["employee_advance"], "REMOTE-ADV-9")
		self.assertEqual(advance["advance_account"], self.remote_account)
		self.assertEqual(post.json["expenses"][0]["default_account"], self.remote_account)
		self.assertNotIn("expense_approver", post.json)
		self.assertNotIn("total_amount_reimbursed", post.json)

	def test_claim_before_its_advance_fails(self):
		site = FakeSite(self.remote())
		with self.assertRaises(CentHRSyncError):
			self.upsert(self.make_claim(), site)

		self.assertEqual(site.writes(), [])
		log = frappe.get_last_doc("CentHR API Logger", {"reference_name": "_T-IOU-CLM-1"})
		self.assertIn("_T-IOU-ADV-1", log.error)

	def test_only_iou_payments_are_synced(self):
		self.assertTrue(is_iou_payment(self.make_payment()))
		self.assertFalse(is_iou_payment(self.make_payment(party_type="Supplier")))
		self.assertFalse(is_iou_payment(self.make_payment(reference_doctype="Journal Entry")))

		with patch("centhr.api.post.payment_entry.enqueue_job") as enqueue:
			enqueue_payment_entry_sync(self.make_payment(party_type="Supplier"))
		enqueue.assert_not_called()

	def test_payment_is_posted_with_target_party_and_reference(self):
		self.log_pushed("Employee Advance", "_T-IOU-ADV-1", "REMOTE-ADV-9")
		site = FakeSite(self.remote())
		self.upsert(self.make_payment(), site)

		[post] = site.writes()
		self.assertEqual(post.json["party"], REMOTE_EMPLOYEE)
		self.assertEqual(post.json["paid_from"], self.remote_account)
		self.assertEqual(post.json["references"][0]["reference_name"], "REMOTE-ADV-9")
		self.assertNotIn("bank_account", post.json)

	def test_cancel_cancels_the_remote_record(self):
		self.log_pushed("Employee Advance", "_T-IOU-ADV-1", "REMOTE-ADV-9")
		site = FakeSite(self.remote(**{"Employee Advance": [{"name": "REMOTE-ADV-9", "docstatus": 1}]}))
		self.upsert(self.make_advance(docstatus=2), site)

		[put] = site.writes()
		self.assertEqual(put.method, "PUT")
		self.assertTrue(put.url.endswith("REMOTE-ADV-9"))
		self.assertEqual(put.json, {"docstatus": 2})
