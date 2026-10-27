# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.migrate.account import AccountMigrator
from centhr.api.migrate.client import PAGE_LENGTH, MigrationError, TargetClient
from centhr.api.migrate.cost_center import CostCenterMigrator
from centhr.api.migrate.leave_type import LeaveTypeMigrator

EXTRA_TEST_RECORD_DEPENDENCIES = []
# The tests mock the CentHR site and use an existing Company, so no test records are needed
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Employee", "Leave Type", "Account", "Cost Center"]

NEW_LEAVE_TYPE = "_Test CentHR Migrated Leave"
EXISTING_LEAVE_TYPE = "_Test CentHR Existing Leave"
NEW_ACCOUNT = "_Test CentHR Migrated Account"
NEW_COST_CENTER = "_Test CentHR Migrated Cost Center"
NEW_ROOT = "_Test CentHR Migrated Root"
# The CentHR site names the company's accounts with another abbreviation than this site
REMOTE_ABBR = "_RMT"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


def fake_target(company):
	return FakeTarget(company=company, base_url="http://centhr.test/", api_key="key")


def fake_site(response, rows=()):
	"""Answer the company abbreviation lookup, `rows` for other lists, and `response` for get_doc."""

	def request(method, url, **kwargs):
		if url.endswith("/Company"):
			return [{"abbr": REMOTE_ABBR}]
		return list(rows) if "params" in kwargs else response

	return request


def to_remote_name(local_name: str) -> str:
	abbr = frappe.get_cached_value("Company", TEST_COMPANY, "abbr")
	return f"{local_name.removesuffix(f' - {abbr}')} - {REMOTE_ABBR}"


@patch("centhr.api.migrate.client.get_target", fake_target)
class IntegrationTestCenthrDataMigrationTool(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		global TEST_COMPANY
		TEST_COMPANY = frappe.get_all("Company", pluck="name", limit=1)[0]

	def setUp(self):
		frappe.db.delete("CentHR API Logger", {"reference_name": NEW_LEAVE_TYPE})
		frappe.db.delete("Leave Type", NEW_LEAVE_TYPE)
		if not frappe.db.exists("Leave Type", EXISTING_LEAVE_TYPE):
			frappe.get_doc({"doctype": "Leave Type", "leave_type_name": EXISTING_LEAVE_TYPE}).insert()

		frappe.db.delete("CentHR API Logger", {"name1": ["in", [NEW_ACCOUNT, NEW_COST_CENTER, NEW_ROOT]]})
		for doctype, filters in (
			("Account", {"account_name": ["in", [NEW_ACCOUNT, NEW_ROOT]]}),
			("Cost Center", {"cost_center_name": NEW_COST_CENTER}),
		):
			for name in frappe.get_all(doctype, filters=filters, pluck="name"):
				frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)

	def test_get_all_reads_every_page(self):
		pages = [[{"name": str(i)} for i in range(size)] for size in (PAGE_LENGTH, PAGE_LENGTH, 120)]
		with patch.object(TargetClient, "request", side_effect=pages) as request:
			records = TargetClient(TEST_COMPANY).get_all("Leave Type", [], ["name"])

		self.assertEqual(len(records), 2 * PAGE_LENGTH + 120)
		starts = [call.kwargs["params"]["limit_start"] for call in request.call_args_list]
		self.assertEqual(starts, [0, PAGE_LENGTH, 2 * PAGE_LENGTH])

	def test_fetch_sets_migration_status(self):
		rows = [
			{"name": EXISTING_LEAVE_TYPE, "leave_type_name": EXISTING_LEAVE_TYPE},
			{"name": NEW_LEAVE_TYPE, "leave_type_name": NEW_LEAVE_TYPE},
		]
		with patch.object(TargetClient, "request", return_value=rows):
			rows = LeaveTypeMigrator(TEST_COMPANY).fetch({})
		status = {row["name"]: row["migration_status"] for row in rows}

		self.assertEqual(status, {EXISTING_LEAVE_TYPE: "Already Exists", NEW_LEAVE_TYPE: "Pending"})

	def test_migrate_creates_record_once(self):
		remote = {"name": NEW_LEAVE_TYPE, "leave_type_name": NEW_LEAVE_TYPE, "max_leaves_allowed": 5}
		with patch.object(TargetClient, "request", return_value=remote):
			first = LeaveTypeMigrator(TEST_COMPANY).migrate(NEW_LEAVE_TYPE)
			second = LeaveTypeMigrator(TEST_COMPANY).migrate(NEW_LEAVE_TYPE)

		self.assertEqual(first.status, "Success")
		self.assertEqual(frappe.db.get_value("Leave Type", NEW_LEAVE_TYPE, "max_leaves_allowed"), 5)
		self.assertEqual(second.status, "Already Exists")

		log = frappe.get_doc("CentHR API Logger", first.log)
		self.assertEqual((log.status, log.target_reference), ("Success", NEW_LEAVE_TYPE))
		self.assertEqual(log.sync_method, "centhr.api.migrate.leave_type.migrate")

		with patch.object(TargetClient, "request", return_value=[remote]):
			[row] = LeaveTypeMigrator(TEST_COMPANY).fetch({})
		self.assertEqual(row["migration_status"], "Success")

	def test_failure_is_logged_and_retryable(self):
		error = MigrationError("HTTP 500: CentHR server error.", {"http_status": 500})
		with patch.object(TargetClient, "request", side_effect=error):
			result = LeaveTypeMigrator(TEST_COMPANY).migrate(NEW_LEAVE_TYPE)

		self.assertEqual(result.status, "Failed")
		self.assertFalse(frappe.db.exists("Leave Type", NEW_LEAVE_TYPE))
		self.assertEqual(frappe.db.get_value("CentHR API Logger", result.log, "status"), "Failed")

		rows = [{"name": NEW_LEAVE_TYPE, "leave_type_name": NEW_LEAVE_TYPE}]
		with patch.object(TargetClient, "request", return_value=rows):
			[row] = LeaveTypeMigrator(TEST_COMPANY).fetch({})
		self.assertEqual((row["migration_status"], row["log"]), ("Failed", result.log))

	def test_missing_mandatory_link_fails(self):
		migrator = LeaveTypeMigrator(TEST_COMPANY)
		employee_field = frappe._dict(fieldname="employee", options="Employee", reqd=1)
		meta = frappe._dict(get_link_fields=lambda: [employee_field])
		with patch.object(migrator.employees, "get_local", return_value=None):
			self.assertRaises(MigrationError, migrator.map_links, meta, {"employee": "HR-EMP-404"})

	def test_migration_does_not_push_back(self):
		from centhr.api.post.attendance import enqueue_attendance_sync

		frappe.flags.centhr_migration = True
		try:
			with patch("frappe.enqueue") as enqueue:
				enqueue_attendance_sync(frappe._dict(company=TEST_COMPANY, name="ATT-1"))
		finally:
			frappe.flags.centhr_migration = False
		enqueue.assert_not_called()

	def test_date_range_is_validated(self):
		with patch.object(TargetClient, "request", return_value=[]):
			self.assertRaises(
				frappe.ValidationError,
				LeaveTypeMigrator(TEST_COMPANY).fetch,
				{"from_date": "2026-02-01", "to_date": "2026-01-01"},
			)

	def test_fetch_lists_accounts_in_tree_order(self):
		root = frappe.db.get_value(
			"Account",
			{"company": TEST_COMPANY, "parent_account": ["is", "not set"]},
			["name", "account_name"],
			as_dict=True,
		)
		rows = [
			{"name": to_remote_name(root.name), "account_name": root.account_name, "company": TEST_COMPANY},
			{"name": f"{NEW_ACCOUNT} - {REMOTE_ABBR}", "account_name": NEW_ACCOUNT, "company": TEST_COMPANY},
		]
		with patch.object(TargetClient, "request", return_value=rows) as request:
			rows = AccountMigrator(TEST_COMPANY).fetch({"root_type": "All"})

		self.assertEqual(request.call_args.kwargs["params"]["order_by"], "lft asc")
		self.assertEqual(
			[(row["migration_status"], row["local_name"]) for row in rows],
			[("Already Exists", root.name), ("Pending", None)],
		)

	def test_account_is_created_under_local_parent(self):
		abbr = frappe.get_cached_value("Company", TEST_COMPANY, "abbr")
		parent = frappe.db.get_value(
			"Account",
			{"company": TEST_COMPANY, "is_group": 1, "parent_account": ["is", "set"], "root_type": "Expense"},
			"name",
		)
		remote = {
			"name": f"{NEW_ACCOUNT} - {REMOTE_ABBR}",
			"account_name": NEW_ACCOUNT,
			"company": TEST_COMPANY,
			"parent_account": to_remote_name(parent),
			"is_group": 0,
			"lft": 9000,
			"rgt": 9001,
		}
		with patch.object(TargetClient, "request", side_effect=fake_site(remote)):
			first = AccountMigrator(TEST_COMPANY).migrate(remote["name"])
			second = AccountMigrator(TEST_COMPANY).migrate(remote["name"])

		self.assertEqual((first.status, first.local_name), ("Success", f"{NEW_ACCOUNT} - {abbr}"))
		self.assertEqual(frappe.db.get_value("Account", first.local_name, "parent_account"), parent)
		self.assertEqual(second.status, "Already Exists")

	def test_parent_is_matched_by_account_name(self):
		parent = frappe.db.get_value(
			"Account",
			{"company": TEST_COMPANY, "is_group": 1, "parent_account": ["is", "set"], "root_type": "Expense"},
			["name", "account_name"],
			as_dict=True,
		)
		# The CentHR site names the parent without the number that it has here
		remote_parent = f"{parent.account_name} - {REMOTE_ABBR}"
		remote = {
			"name": f"{NEW_ACCOUNT} - {REMOTE_ABBR}",
			"account_name": NEW_ACCOUNT,
			"company": TEST_COMPANY,
			"parent_account": remote_parent,
			"is_group": 0,
		}
		rows = [{"name": remote_parent, "account_name": parent.account_name}]
		with patch.object(TargetClient, "request", side_effect=fake_site(remote, rows)):
			result = AccountMigrator(TEST_COMPANY).migrate(remote["name"])

		self.assertEqual(result.status, "Success")
		self.assertEqual(frappe.db.get_value("Account", result.local_name, "parent_account"), parent.name)

	def test_remote_root_is_created_under_local_root(self):
		local_root = frappe.db.get_value(
			"Account",
			{"company": TEST_COMPANY, "parent_account": ["is", "not set"], "root_type": "Income"},
			"name",
		)
		for is_group in (1, 0):
			remote = {
				"name": f"{NEW_ROOT} - {REMOTE_ABBR}",
				"account_name": NEW_ROOT,
				"company": TEST_COMPANY,
				"root_type": "Income",
				"is_group": is_group,
			}
			with patch.object(TargetClient, "request", side_effect=fake_site(remote)):
				result = AccountMigrator(TEST_COMPANY).migrate(remote["name"])

			self.assertEqual(result.status, "Success")
			self.assertEqual(frappe.db.get_value("Account", result.local_name, "parent_account"), local_root)
			self.assertIn(local_root, frappe.db.get_value("CentHR API Logger", result.log, "error"))
			frappe.delete_doc("Account", result.local_name, force=True, ignore_permissions=True)

	def test_account_without_parent_fails(self):
		remote = {
			"name": f"{NEW_ACCOUNT} - {REMOTE_ABBR}",
			"account_name": NEW_ACCOUNT,
			"company": TEST_COMPANY,
			"parent_account": f"_Test CentHR Missing Parent - {REMOTE_ABBR}",
			"is_group": 1,
			"root_type": "Expense",
		}
		with patch.object(TargetClient, "request", side_effect=fake_site(remote)):
			result = AccountMigrator(TEST_COMPANY).migrate(remote["name"])

		self.assertEqual(result.status, "Failed")
		self.assertIn("does not exist on this site", result.error)
		# A child without its parent must not become a new root
		self.assertFalse(frappe.db.exists("Account", {"account_name": NEW_ACCOUNT}))

	def test_cost_center_is_created_once(self):
		root = frappe.db.get_value(
			"Cost Center", {"company": TEST_COMPANY, "parent_cost_center": ["is", "not set"]}, "name"
		)
		remote = {
			"name": f"{NEW_COST_CENTER} - {REMOTE_ABBR}",
			"cost_center_name": NEW_COST_CENTER,
			"company": TEST_COMPANY,
			"parent_cost_center": to_remote_name(root),
			"is_group": 0,
		}
		with patch.object(TargetClient, "request", side_effect=fake_site(remote)):
			first = CostCenterMigrator(TEST_COMPANY).migrate(remote["name"])
			second = CostCenterMigrator(TEST_COMPANY).migrate(remote["name"])

		self.assertEqual(first.status, "Success")
		self.assertEqual(frappe.db.get_value("Cost Center", first.local_name, "parent_cost_center"), root)
		self.assertEqual(second.status, "Already Exists")
