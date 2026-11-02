import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.bulk_salary_structure_assignment import get_tool


class TestBulkSalaryStructureAssignment(IntegrationTestCase):
	def test_tool_keeps_only_its_own_fields(self):
		tool = get_tool({"from_date": "2026-11-15", "company": "X", "not_a_field": 1})

		self.assertEqual(tool.from_date, "2026-11-15")
		self.assertEqual(tool.company, "X")
		self.assertIsNone(tool.get("not_a_field"))

	def test_user_without_access_is_refused(self):
		with self.set_user("Guest"), self.assertRaises(frappe.PermissionError):
			get_tool({"from_date": "2026-11-15"})
