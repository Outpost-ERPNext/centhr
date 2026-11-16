from datetime import date
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.pms import kpi
from centhr.pms.period import KpiMonth
from centhr.pms.scoring import kpi_remark, score_kpi_result
from centhr.pms.testing import (
	KPI_ITEMS,
	get_fiscal_year_2031,
	make_department,
	make_employee,
	make_settings,
	make_uom,
	make_user,
)

# The employees, users and settings are created in the test transaction and rolled back with it
ITEMS = KPI_ITEMS


def row(**values):
	return frappe._dict(
		{"target": 100, "achieved": 0, "weight": 50, "polarity": "Positive", "not_measured": 0, **values}
	)


class TestKpiScoring(IntegrationTestCase):
	def test_higher_is_better(self):
		rows = [row(achieved=80), row(achieved=50)]

		self.assertEqual(score_kpi_result(rows), 65)
		self.assertEqual([(r.percent, r.weighted_score) for r in rows], [(80, 40), (50, 25)])

	def test_lower_is_better(self):
		# 4 against a target of 5 beats the target; 10 is half as good; 0 is the best outcome
		rows = [
			row(polarity="Negative", target=5, achieved=10),
			row(polarity="Negative", target=5, achieved=0),
		]

		self.assertEqual(score_kpi_result(rows), 75)
		self.assertEqual([r.weighted_score for r in rows], [25, 50])

	def test_a_row_never_earns_more_than_its_weight(self):
		rows = [row(achieved=300), row(achieved=50)]

		self.assertEqual(score_kpi_result(rows), 75)
		self.assertEqual(rows[0].percent, 300)

	def test_not_measured_rows_earn_nothing(self):
		self.assertEqual(score_kpi_result([row(achieved=100), row(achieved=100, not_measured=1)]), 50)

	def test_untouched_result_is_not_scored(self):
		self.assertEqual(score_kpi_result([row(), row()]), 0)

	def test_remark_comes_from_the_bands(self):
		bands = [frappe._dict(score="0-50", remark="Below"), frappe._dict(score="51-100", remark="Met")]

		self.assertEqual(kpi_remark(0, bands), "Not Captured")
		self.assertEqual(kpi_remark(50, bands), "Below")
		self.assertEqual(kpi_remark(88.5, bands), "Met")
		# Between two bands
		self.assertEqual(kpi_remark(50.5, bands), "Good Performance")


class TestKpiCycle(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		cls.addClassCleanup(frappe.clear_document_cache, "PMS Settings", cls.company)
		cls.fiscal_year = get_fiscal_year_2031()
		make_settings(cls.company)
		make_uom()

		cls.department = make_department(cls.company, "_Test PMS Sales")
		cls.manager = make_employee(
			cls.company, "Meena", cls.department, roles=["PMS Line Manager", "PMS User"]
		)
		cls.report = make_employee(cls.company, "Ravi", cls.department, cls.manager.name, roles=["PMS User"])
		cls.other = make_employee(cls.company, "Asha", cls.department, roles=["PMS Line Manager", "PMS User"])
		cls.hr_user = make_user("pms-hr", ["HR Manager"])

	def setUp(self):
		frappe.set_user("Administrator")

	def make_template(self, employee=None, month="Mar", items=ITEMS, submit=True):
		template = kpi.make_template(
			KpiMonth(self.fiscal_year, month), (employee or self.report).name, items
		).insert()
		return template.submit() or template if submit else template

	def get_result(self, template):
		return frappe.get_doc("KPI Result", {"kpi_template": template.name})

	# Template

	def test_template_takes_the_employee_details(self):
		template = self.make_template(submit=False)

		self.assertEqual(template.name, f"KPI-T|03-{self.fiscal_year}|{self.report.name}")
		self.assertEqual((template.company, template.department), (self.company, self.department))
		self.assertEqual(template.reviewer, self.manager.name)
		self.assertEqual(template.total_weight, 100)

	def test_one_template_per_employee_and_month(self):
		self.make_template(month="Apr", submit=False)

		with self.assertRaises(frappe.ValidationError):
			self.make_template(month="Apr", submit=False)

	def test_weights_cannot_exceed_100(self):
		items = [{**ITEMS[0], "weight": "70"}, ITEMS[1]]

		with self.assertRaises(frappe.ValidationError):
			self.make_template(month="May", items=items, submit=False)

	def test_frozen_month_cannot_change(self):
		frappe.db.set_value("PMS Settings", self.company, "kpi_freeze_day", 2)
		frappe.clear_document_cache("PMS Settings", self.company)
		self.addCleanup(frappe.db.set_value, "PMS Settings", self.company, "kpi_freeze_day", 0)
		self.addCleanup(frappe.clear_document_cache, "PMS Settings", self.company)
		frappe.set_user(self.hr_user)

		with patch("centhr.pms.kpi.today", return_value="2031-07-03"):
			with self.assertRaises(frappe.ValidationError):
				self.make_template(month="Jun", submit=False)
		with patch("centhr.pms.kpi.today", return_value="2031-07-02"):
			self.make_template(month="Jun", submit=False)

	# Result

	def test_submitting_a_template_creates_the_draft_result(self):
		template = self.make_template(month="Jul")
		result = self.get_result(template)

		self.assertEqual(result.name, f"KPI-R|07-{self.fiscal_year}|{self.report.name}")
		self.assertEqual(result.docstatus, 0)
		self.assertEqual(
			[(r.kpi, r.target, r.weight, r.polarity) for r in result.items],
			[
				("Sales closed", 100, "60", "Positive"),
				("Complaints", 5, "40", "Negative"),
			],
		)
		self.assertEqual((result.overall_score, result.remark), (0, "Not Captured"))

	def test_result_is_scored_and_keeps_the_template_targets(self):
		result = self.get_result(self.make_template(month="Aug"))
		result.items[0].achieved = 90
		result.items[1].achieved = 4
		# A manager cannot make the target easier
		result.items[0].target = 10
		result.save()

		self.assertEqual(result.items[0].target, 100)
		self.assertEqual([r.weighted_score for r in result.items], [54, 40])
		self.assertEqual((result.overall_score, result.remark), (94, "Met"))

	def test_result_needs_every_achieved_value_to_submit(self):
		result = self.get_result(self.make_template(month="Sep"))
		result.items[1].achieved = 5

		with self.assertRaises(frappe.ValidationError):
			result.submit()

		result.reload()
		result.items[0].not_measured = 1
		result.items[1].achieved = 5
		result.submit()
		self.assertEqual(result.overall_score, 40)

	def test_cancelling_a_result_reopens_the_template(self):
		template = self.make_template(month="Oct")
		result = self.get_result(template)
		result.items[0].achieved = 100
		result.submit()
		result.cancel()

		self.assertEqual(frappe.db.get_value("KPI Template", template.name, "docstatus"), 2)

	def test_cancelling_a_template_removes_its_draft_result(self):
		template = self.make_template(month="Nov")
		template.cancel()

		self.assertFalse(frappe.db.exists("KPI Result", {"kpi_template": template.name}))

	# Who sees what

	def test_line_manager_fills_in_direct_reports_only(self):
		result = self.get_result(self.make_template(month="Dec"))
		own = self.get_result(self.make_template(employee=self.manager, month="Dec"))

		def can(ptype, doc, employee):
			return bool(frappe.has_permission("KPI Result", ptype, doc=doc, user=employee.user_id))

		self.assertTrue(can("write", result, self.manager))
		self.assertTrue(can("submit", result, self.manager))
		# Their own result is filled in by their manager
		self.assertTrue(can("read", own, self.manager))
		self.assertFalse(can("write", own, self.manager))
		# The employee reads their own result; another manager sees nothing of it
		self.assertTrue(can("read", result, self.report))
		self.assertFalse(can("write", result, self.report))
		self.assertFalse(can("read", result, self.other))
		self.assertTrue(can("write", result, frappe._dict(user_id=self.hr_user)))

	def test_lists_show_own_and_direct_reports(self):
		self.make_template(month="Jan")
		self.make_template(employee=self.manager, month="Jan")
		self.make_template(employee=self.other, month="Jan")

		def listed(user):
			frappe.set_user(user)
			try:
				return set(
					frappe.get_list(
						"KPI Result",
						filters={"fiscal_year": self.fiscal_year, "month": "Jan"},
						pluck="employee",
					)
				)
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(listed(self.manager.user_id), {self.manager.name, self.report.name})
		self.assertEqual(listed(self.report.user_id), {self.report.name})
		self.assertEqual(listed(self.other.user_id), {self.other.name})
		self.assertEqual(listed(self.hr_user), {self.manager.name, self.report.name, self.other.name})

	# Bulk creation

	def test_department_templates_skip_employees_who_have_one(self):
		month = KpiMonth(self.fiscal_year, "Feb")
		self.make_template(month="Feb", submit=False)

		outcome = kpi.DepartmentTemplates(month, self.department, ITEMS).create()

		self.assertEqual(outcome["skipped"], 1)
		self.assertEqual(len(outcome["created"]), 2)
		self.assertEqual(
			kpi.get_employees_with_template(month, [self.manager.name, self.other.name, self.report.name]),
			{self.manager.name, self.other.name, self.report.name},
		)

	def test_monthly_copy_makes_drafts_from_last_months_submitted_templates(self):
		department = make_department(self.company, "_Test PMS Copy")
		stays = make_employee(self.company, "Kofi", department)
		left = make_employee(self.company, "Lara", department)
		for employee in (stays, left):
			self.make_template(employee=employee, month="Mar")
		frappe.db.set_value("Employee", left.name, "status", "Left")

		created = kpi.MonthlyCopy(self.company, "2031-04-27").run()

		copies = frappe.get_all(
			"KPI Template", filters={"name": ["in", created]}, fields=["employee", "month", "docstatus"]
		)
		self.assertIn({"employee": stays.name, "month": "Apr", "docstatus": 0}, copies)
		self.assertNotIn(left.name, [c.employee for c in copies])
		# A second run finds nothing left to copy for them
		self.assertEqual(kpi.MonthlyCopy(self.company, "2031-04-27").run(), [])


class TestKpiMonth(IntegrationTestCase):
	def test_month_dates_follow_the_fiscal_year(self):
		fiscal_year = frappe._dict(year_start_date=date(2031, 4, 1), year_end_date=date(2032, 3, 31))

		with patch("centhr.pms.period.frappe.get_cached_value", return_value=tuple(fiscal_year.values())):
			self.assertEqual(KpiMonth("2031-2032", "Apr").start, date(2031, 4, 1))
			self.assertEqual(KpiMonth("2031-2032", "Jan").start, date(2032, 1, 1))
			self.assertEqual(KpiMonth("2031-2032", "Dec").freeze_date(2), date(2032, 1, 2))
			self.assertEqual(KpiMonth("2031-2032", "Jan").freeze_date(31), date(2032, 2, 29))
