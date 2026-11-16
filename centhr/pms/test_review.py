from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.pms import review, reviewer, score_sheet
from centhr.pms.overall import OverallScores
from centhr.pms.scoring import average_rating, rating_score, review_score
from centhr.pms.testing import (
	get_fiscal_year_2031,
	make_department,
	make_employee,
	make_settings,
	make_uom,
	submit_kpi_result,
)

QUARTER = "Q1"
QUESTIONS = [{"question": "Works well with the team?"}, {"question": "Delivers on time?"}]
MAPPING = "PMS Employee Relationship"


class TestReviewScoring(IntegrationTestCase):
	def test_average_is_rounded_to_the_nearest_half(self):
		self.assertEqual(average_rating([4, 5]), 4.5)
		self.assertEqual(average_rating([4, 4, 5]), 4.5)
		self.assertEqual(average_rating([3, 3, 4, 3]), 3.0)

	def test_rating_score_is_the_percentage_times_the_weight(self):
		self.assertEqual(rating_score(4.5, 60), 54)
		self.assertEqual(rating_score(3.5, 40), 28)

	def test_review_score_weighs_each_review(self):
		# The line manager at 60 and one peer at 40
		self.assertEqual(review_score([(54, 60), (28, 40)]), 82.0)
		# A second peer counts as much as the first
		self.assertEqual(review_score([(54, 60), (28, 40), (40, 40)]), 87.14)
		self.assertIsNone(review_score([]))


class TestReviewCycle(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		cls.addClassCleanup(frappe.clear_document_cache, "PMS Settings", cls.company)
		cls.fiscal_year = get_fiscal_year_2031()
		make_uom()
		make_settings(cls.company)
		settings = frappe.get_doc("PMS Settings", cls.company)
		settings.set(
			"overall_score",
			[{"score": "0-59", "remark": "Needs work"}, {"score": "60-100", "remark": "Strong"}],
		)
		settings.set(
			"increments",
			[
				{"score": "0-59", "status": "PIP"},
				{"score": "60-100", "status": "Increment", "increment_": "10"},
			],
		)
		settings.save()

	def setUp(self):
		frappe.set_user("Administrator")

	def make_team(self, name: str, roles=None):
		"""A department in the quarter's 360 review: a boss, and Ann, Ben and Cal who report to the boss
		and are each other's peers. Ann has a submitted KPI Result of 94 for January."""
		department = make_department(self.company, f"_Test PMS {name}")
		boss = make_employee(self.company, f"{name}Boss", department, roles=roles)
		ann, ben, cal = (
			make_employee(self.company, f"{name}{n}", department, boss.name, roles=roles)
			for n in ("Ann", "Ben", "Cal")
		)
		self.add_to_review(department)
		frappe.get_doc(
			{
				"doctype": MAPPING,
				"employee": ann.name,
				"peers": [{"employee": ben.name}, {"employee": cal.name}],
			}
		).insert()
		submit_kpi_result(ann.name, self.fiscal_year, "Jan", (90, 4))
		return frappe._dict(department=department, boss=boss, ann=ann, ben=ben, cal=cal)

	def add_to_review(self, department: str) -> None:
		period = {"company": self.company, "fiscal_year": self.fiscal_year, "quarter": QUARTER}
		name = frappe.db.get_value("PMS 360 Degree", period, "name")
		setup = (
			frappe.get_doc("PMS 360 Degree", name)
			if name
			else frappe.get_doc({"doctype": "PMS 360 Degree", **period})
		)
		setup.append("departments", {"department": department, "superior_weight": 60, "peers_weight": 40})
		setup.save()

	def build(self, team, questions=QUESTIONS, preview=False):
		return review.QuestionnaireBuilder(
			self.company, self.fiscal_year, QUARTER, questions, [team.department]
		).run(preview=preview)

	def close(self, team) -> list[str]:
		self.build(team)
		return review.close_questionnaire(self.questionnaire_of(team.ann))

	def questionnaire_of(self, employee) -> str:
		return frappe.db.get_value(
			"PMS Questionnaire",
			{"employee": employee.name, "fiscal_year": self.fiscal_year, "quarter": QUARTER},
		)

	def allocation_of(self, team, reviewer_employee) -> str:
		return frappe.db.get_value(
			"PMS Form Allocation",
			{"reviewee": team.ann.name, "reviewer": reviewer_employee.name, "docstatus": 1},
		)

	def give(self, team, reviewer_employee, ratings):
		return reviewer.submit_review(
			self.allocation_of(team, reviewer_employee),
			reviewer_employee.name,
			[{"rating": r} for r in ratings],
		)

	# Create PMS Form

	def test_only_employees_with_a_kpi_result_get_a_questionnaire(self):
		team = self.make_team("Form")

		preview = self.build(team, preview=True)
		self.assertEqual(preview.created, [team.ann.name])
		self.assertEqual(len(preview.skipped), 3)
		self.assertIsNone(self.questionnaire_of(team.ann))

		self.build(team)
		questions = frappe.get_doc(
			"PMS Questionnaire", self.questionnaire_of(team.ann)
		).pms_questionnaire_list
		self.assertEqual([row.question for row in questions], [q["question"] for q in QUESTIONS])

	def test_an_open_questionnaire_gets_only_the_new_questions(self):
		team = self.make_team("More")
		self.build(team)

		outcome = self.build(team, [*QUESTIONS, {"question": "Shares knowledge?"}])

		self.assertEqual(outcome.updated, [team.ann.name])
		questionnaire = frappe.get_doc("PMS Questionnaire", self.questionnaire_of(team.ann))
		self.assertEqual(len(questionnaire.pms_questionnaire_list), 3)

	def test_a_quarter_without_a_360_review_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			review.QuestionnaireBuilder(self.company, self.fiscal_year, "Q4", QUESTIONS)

	# Closing

	def test_closing_asks_the_line_manager_and_the_peers(self):
		team = self.make_team("Close")

		self.close(team)

		asked = frappe.get_all(
			"PMS Form Allocation",
			filters={"reviewee": team.ann.name, "docstatus": 1},
			fields=["reviewer", "relationship_type", "status"],
		)
		self.assertCountEqual(
			[(a.reviewer, a.relationship_type, a.status) for a in asked],
			[
				(team.boss.name, "Line Manager", "Pending"),
				(team.ben.name, "Peers", "Pending"),
				(team.cal.name, "Peers", "Pending"),
			],
		)
		self.assertEqual(
			frappe.db.get_value("PMS Questionnaire", self.questionnaire_of(team.ann), "status"), "Completed"
		)
		with self.assertRaises(frappe.ValidationError):
			review.close_questionnaire(self.questionnaire_of(team.ann))

	def test_closing_several_reports_the_ones_that_fail(self):
		team = self.make_team("Many")
		submit_kpi_result(team.ben.name, self.fiscal_year, "Feb", (100, 5))
		self.build(team)
		# Ben has no peer mapping of his own that names a line manager or peers who can review
		frappe.delete_doc(MAPPING, team.ben.name, force=True)

		outcome = review.close_questionnaires(
			[self.questionnaire_of(team.ann), self.questionnaire_of(team.ben)]
		)

		self.assertEqual(outcome.closed, [self.questionnaire_of(team.ann)])
		self.assertEqual(len(outcome.failed), 1)
		self.assertEqual(
			frappe.db.get_value("PMS Questionnaire", self.questionnaire_of(team.ben), "status"), "Open"
		)

	def test_reopening_is_allowed_until_somebody_reviews(self):
		team = self.make_team("Reopen")
		self.close(team)
		name = self.questionnaire_of(team.ann)

		review.reopen_questionnaire(name)
		self.assertEqual(frappe.db.get_value("PMS Questionnaire", name, "status"), "Open")
		self.assertFalse(frappe.db.exists("PMS Form Allocation", {"form_reference": name, "docstatus": 1}))

		review.close_questionnaire(name)
		self.give(team, team.boss, [4, 5])
		with self.assertRaises(frappe.ValidationError):
			review.reopen_questionnaire(name)

	def test_a_changed_peer_mapping_changes_who_is_asked(self):
		team = self.make_team("Swap")
		dan = make_employee(self.company, "SwapDan", team.department, team.boss.name, roles=None)
		self.close(team)
		self.give(team, team.ben, [3, 4])

		mapping = frappe.get_doc(MAPPING, team.ann.name)
		mapping.set("peers", [{"employee": dan.name}])
		mapping.save()

		# Cal had not reviewed yet and is no longer asked; Ben's review stands; Dan is asked now
		self.assertIsNone(self.allocation_of(team, team.cal))
		self.assertIsNotNone(self.allocation_of(team, team.ben))
		self.assertIsNotNone(self.allocation_of(team, dan))

	# Reviewing

	def test_a_review_is_scored_with_the_reviewers_weight(self):
		team = self.make_team("Score")
		self.close(team)

		by_boss = frappe.get_doc("PMS Question Form", self.give(team, team.boss, [4, 5]))
		by_ben = frappe.get_doc("PMS Question Form", self.give(team, team.ben, [3, 4]))

		self.assertEqual((by_boss.average_rating, by_boss.rating_score), (4.5, 54))
		self.assertEqual((by_ben.average_rating, by_ben.rating_score), (3.5, 28))
		self.assertEqual(
			[row.question for row in by_boss.pms_questionnaire_list], [q["question"] for q in QUESTIONS]
		)
		allocation = frappe.db.get_value("PMS Form Allocation", self.allocation_of(team, team.boss), "status")
		self.assertEqual(allocation, "Completed")

	def test_only_the_reviewer_can_review_and_only_once(self):
		team = self.make_team("Guard")
		self.close(team)
		for_cal = self.allocation_of(team, team.cal)

		with self.assertRaises(frappe.PermissionError):
			reviewer.submit_review(for_cal, team.ben.name, [{"rating": 5}, {"rating": 5}])
		with self.assertRaises(frappe.PermissionError):
			reviewer.get_review_form(for_cal, team.ann.name)
		for ratings in ([6, 5], [0, 5], [3.5, 4], [5]):
			with self.assertRaises(frappe.ValidationError, msg=ratings):
				self.give(team, team.cal, ratings)

		self.give(team, team.cal, [5, 5])
		with self.assertRaises(frappe.ValidationError):
			self.give(team, team.cal, [5, 5])

	def test_a_reviewer_sees_what_they_are_asked(self):
		team = self.make_team("Mine")
		self.close(team)

		mine = reviewer.get_my_reviews(team.ben.name)
		form = reviewer.get_review_form(mine[0].name, team.ben.name)

		self.assertEqual([(m.reviewee, m.status) for m in mine], [(team.ann.name, "Pending")])
		self.assertEqual([q.question for q in form["questions"]], [q["question"] for q in QUESTIONS])
		self.assertEqual(form["ratings"], [])

	# Results

	def test_overall_score_joins_the_kpi_and_360_scores(self):
		team = self.make_team("Overall")
		self.close(team)
		self.give(team, team.boss, [4, 5])
		self.give(team, team.ben, [3, 4])

		rows = OverallScores(self.fiscal_year, quarter=QUARTER, department=team.department).get_rows()
		ann = next(row for row in rows if row["employee"] == team.ann.name)

		# KPI 94 at 70% and 360 score 82 at 30%
		self.assertEqual((ann["kpi_score"], ann["review_score"]), (94, 82))
		self.assertEqual((ann["reviews_done"], ann["reviews_total"]), (2, 3))
		self.assertEqual((ann["overall_score"], ann["overall_remark"]), (90.4, "Strong"))
		# Ben has neither score yet
		ben = next(row for row in rows if row["employee"] == team.ben.name)
		self.assertIsNone(ben["overall_score"])

	def test_a_line_manager_sees_only_direct_reports(self):
		team = self.make_team("Scope", roles=("PMS User",))

		def listed(employee) -> set[str]:
			frappe.set_user(employee.user_id)
			try:
				return {
					row["employee"] for row in OverallScores(self.fiscal_year, quarter=QUARTER).get_rows()
				}
			finally:
				frappe.set_user("Administrator")

		self.assertEqual(listed(team.boss), {team.ann.name, team.ben.name, team.cal.name})
		self.assertEqual(listed(team.ann), set())

	def test_score_sheet_gives_the_increment_of_the_final_score(self):
		team = self.make_team("Sheet")
		self.close(team)
		self.give(team, team.boss, [4, 5])
		self.give(team, team.ben, [3, 4])

		with patch(
			"centhr.centhr.doctype.pms_score_sheet.pms_score_sheet.get_current_ctc",
			return_value=(1000.0, None),
		):
			outcome = score_sheet.generate(self.company, self.fiscal_year, QUARTER)
			sheet = frappe.get_doc("PMS Score Sheet", {"employee": team.ann.name})
			self.assertIn(sheet.name, outcome["created"])
			self.assertEqual(
				(sheet.calculated_score, sheet.outcome, sheet.increment), (90.4, "Increment", 10)
			)
			self.assertEqual((sheet.old_ctc, sheet.new_ctc, sheet.ctc_impact), (1000, 1100, 100))
			# Nothing new on a second run
			self.assertEqual(score_sheet.generate(self.company, self.fiscal_year, QUARTER)["created"], [])

			# HR lowers the score: it now falls in the PIP band and earns no increment
			sheet.check_normalized_score = 1
			sheet.normalized_score = 40
			sheet.save()
			self.assertEqual((sheet.outcome, sheet.increment, sheet.new_ctc), ("PIP", 0, 1000))

			sheet.submit()
		self.assertEqual((sheet.docstatus, sheet.status), (1, "Approved"))

	def test_a_score_sheet_can_be_rejected(self):
		team = self.make_team("Reject")
		sheet = frappe.get_doc(
			{
				"doctype": "PMS Score Sheet",
				"employee": team.ann.name,
				"fiscal_year": self.fiscal_year,
				"quarter": QUARTER,
				"calculated_score": 30,
			}
		).insert()

		sheet.reject()

		self.assertEqual((sheet.docstatus, sheet.status, sheet.outcome), (0, "Rejected", "PIP"))
