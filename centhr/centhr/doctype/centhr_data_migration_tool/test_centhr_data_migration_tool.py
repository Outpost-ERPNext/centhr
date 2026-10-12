# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.migrate.client import PAGE_LENGTH, MigrationError, TargetClient
from centhr.api.migrate.leave_type import LeaveTypeMigrator

EXTRA_TEST_RECORD_DEPENDENCIES = []
# The tests mock the CentHR site and use an existing Company, so no test records are needed
IGNORE_TEST_RECORD_DEPENDENCIES = ["Company", "Employee", "Leave Type"]

NEW_LEAVE_TYPE = "_Test CentHR Migrated Leave"
EXISTING_LEAVE_TYPE = "_Test CentHR Existing Leave"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


def fake_target(company):
	return FakeTarget(company=company, base_url="http://centhr.test/", api_key="key")


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
