# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.common.target_client import TargetClient
from centhr.api.department import delete_department, enqueue_department_sync, sync_department

PARENT = "_Test CentHR Sync Parent"
CHILD = "_Test CentHR Sync Child"
# The entity site names the company's departments with another abbreviation than this site
REMOTE_ABBR = "_RMT"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


class FakeSite:
	"""Answers GET with `remote` departments that match the filters, and records every request."""

	def __init__(self, remote=()):
		self.remote = list(remote)
		self.calls = []

	def __call__(self, method, url, **kwargs):
		self.calls.append(frappe._dict(method=method, url=url, json=kwargs.get("json")))
		if method == "GET":
			filters = frappe.parse_json(kwargs["params"]["filters"])
			return [{"name": row["name"], "docstatus": 0} for row in self.remote if matches(row, filters)]
		if method in ("POST", "PUT"):
			return {"name": f"{kwargs['json']['department_name']} - {REMOTE_ABBR}"}
		return None

	def writes(self):
		return [call for call in self.calls if call.method != "GET"]


def matches(row: dict, filters: list) -> bool:
	return all(
		not row.get(field) if operator == "is" else row.get(field) == value
		for field, operator, value in filters
	)


def remote_department(department_name: str) -> dict:
	return {
		"name": f"{department_name} - {REMOTE_ABBR}",
		"department_name": department_name,
		"company": TEST_COMPANY,
	}


# The tests mock the entity site and use an existing Company, so no test records are needed
class IntegrationTestDepartmentSync(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		global TEST_COMPANY
		TEST_COMPANY = frappe.get_all("Company", pluck="name", limit=1)[0]

	def setUp(self):
		self.targets = patch(
			"centhr.api.common.record_sync.get_targets",
			return_value=[FakeTarget(company=TEST_COMPANY, base_url="http://entity.test/", api_key="key")],
		)
		self.targets.start()
		self.addCleanup(self.targets.stop)

		# no jobs while the test records are made
		with patch("centhr.api.department.enqueue_job"):
			self.parent = self.make_department(PARENT, is_group=1)
			self.child = self.make_department(CHILD, parent_department=self.parent.name)

	def make_department(self, department_name: str, **values):
		name = frappe.db.get_value("Department", {"department_name": department_name, "company": TEST_COMPANY})
		if name:
			return frappe.get_doc("Department", name)
		return frappe.get_doc(
			{"doctype": "Department", "department_name": department_name, "company": TEST_COMPANY, **values}
		).insert()

	def sync(self, site: FakeSite):
		with patch.object(TargetClient, "request", side_effect=site):
			sync_department(self.child.name)

	def test_new_department_is_posted_with_the_remote_parent(self):
		site = FakeSite([remote_department(PARENT)])
		self.sync(site)

		[post] = site.writes()
		self.assertEqual(post.method, "POST")
		self.assertEqual(
			set(post.json), {"department_name", "parent_department", "company", "is_group", "disabled"}
		)
		self.assertEqual(post.json["parent_department"], f"{PARENT} - {REMOTE_ABBR}")

	def test_department_with_another_abbreviation_is_updated(self):
		site = FakeSite([remote_department(PARENT), remote_department(CHILD)])
		self.sync(site)

		[put] = site.writes()
		self.assertEqual(put.method, "PUT")
		self.assertTrue(put.url.endswith(frappe.utils.quote(f"{CHILD} - {REMOTE_ABBR}", safe="")))

	def test_missing_parent_fails(self):
		site = FakeSite()
		self.sync(site)

		self.assertEqual(site.writes(), [])
		log = frappe.get_last_doc(
			"CentHR API Logger", {"doctypes": "Department", "reference_name": self.child.name}
		)
		self.assertEqual(log.status, "Failed")
		self.assertIn(PARENT, log.error)

	def test_delete_finds_the_department_by_name_and_company(self):
		site = FakeSite([remote_department(CHILD)])
		with patch.object(TargetClient, "request", side_effect=site):
			delete_department(
				self.child.name,
				TEST_COMPANY,
				CHILD,
				{"department_name": CHILD, "company": TEST_COMPANY},
			)

		[delete] = site.writes()
		self.assertEqual(delete.method, "DELETE")
		self.assertTrue(delete.url.endswith(frappe.utils.quote(f"{CHILD} - {REMOTE_ABBR}", safe="")))

	def test_company_without_targets_is_not_synced(self):
		with (
			patch("centhr.api.common.record_sync.get_targets", return_value=[]),
			patch("frappe.enqueue") as enqueue,
		):
			enqueue_department_sync(self.child)

		enqueue.assert_not_called()
