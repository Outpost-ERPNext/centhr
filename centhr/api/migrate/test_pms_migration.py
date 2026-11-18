from unittest.mock import patch
from urllib.parse import unquote

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.migrate.client import MigrationError, TargetClient
from centhr.api.migrate.kpi_result import KpiResultMigrator
from centhr.api.migrate.kpi_template import KpiTemplateMigrator
from centhr.api.migrate.kpi_uom import KpiUomMigrator
from centhr.api.migrate.pms_360_degree import Pms360DegreeMigrator
from centhr.api.migrate.pms_employee_relationship import PmsEmployeeRelationshipMigrator
from centhr.api.migrate.pms_form_allocation import PmsFormAllocationMigrator
from centhr.api.migrate.pms_question import PmsQuestionMigrator
from centhr.api.migrate.pms_question_form import PmsQuestionFormMigrator
from centhr.api.migrate.pms_question_trait import PmsQuestionTraitMigrator
from centhr.api.migrate.pms_questionnaire import PmsQuestionnaireMigrator
from centhr.api.migrate.pms_score_sheet import PmsScoreSheetMigrator
from centhr.api.migrate.pms_settings import PmsSettingsMigrator
from centhr.pms.overall import OverallScores
from centhr.pms.testing import get_fiscal_year_2031, make_department, make_employee

# The CentHR site is simulated (see FakeSite); everything created here is rolled back with the test
UOM = "_Test Mig %"
TRAIT = "_Test Mig Teamwork"
QUESTION = "Works well with the team? (migration test)"
ANN, BEN, BOSS = "HR-EMP-ANN", "HR-EMP-BEN", "HR-EMP-BOSS"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


class FakeSite:
	"""Answers the REST calls of TargetClient from a dict of {DocType: {name: record}}."""

	def __init__(self, company: str, records: dict):
		self.abbr = frappe.get_cached_value("Company", company, "abbr")
		self.records = records

	def request(self, method, url, **kwargs):
		doctype, _, name = unquote(url.split("/api/resource/")[1]).partition("/")
		docs = self.records.get(doctype, {})
		if "params" in kwargs:
			# Lists ignore their filters: the migrators only take what they asked about
			return (
				[{"abbr": self.abbr}]
				if doctype == "Company"
				else [{"name": n, **doc} for n, doc in docs.items()]
			)
		if name not in docs:
			raise MigrationError(f"HTTP 404: {doctype} {name}")
		return {"name": name, "doctype": doctype, **docs[name]}


class TestPmsMigration(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		cls.addClassCleanup(frappe.clear_document_cache, "PMS Settings", cls.company)
		cls.fiscal_year = get_fiscal_year_2031()
		cls.department = make_department(cls.company, "_Test PMS Migration")
		cls.boss = cls.make_local("Boss", BOSS)
		cls.ann = cls.make_local("Ann", ANN, cls.boss.name)
		cls.ben = cls.make_local("Ben", BEN, cls.boss.name)
		cls.site = FakeSite(cls.company, cls.remote_records())
		cls.enterClassContext(
			patch(
				"centhr.api.migrate.client.get_target",
				lambda company: FakeTarget(base_url="http://centhr.test", api_key="key"),
			)
		)
		cls.enterClassContext(patch.object(TargetClient, "request", cls.site.request))

	@classmethod
	def make_local(cls, name: str, remote_id: str, reports_to: str | None = None):
		"""An employee here whose Employee Number is their ID on the CentHR site, as after the Employee tab."""
		employee = make_employee(cls.company, f"Mig{name}", cls.department, reports_to, roles=None)
		employee.db_set("employee_number", remote_id)
		return employee

	@classmethod
	def remote_records(cls) -> dict:
		period = {"fiscal_year": cls.fiscal_year, "quarter": "Q1"}
		questionnaire = f"PMS-{cls.fiscal_year}-Q1-{ANN}"
		by_boss, by_ben = f"PMS|{cls.fiscal_year}|{ANN}|{BOSS}|1", f"PMS|{cls.fiscal_year}|{ANN}|{BEN}|1"
		kpi = {
			"employee": ANN,
			"fiscal_year": cls.fiscal_year,
			"month": "Jan",
			"department": cls.department,
			"docstatus": 1,
		}
		rows = [
			{"kpi": "Sales closed", "uom": UOM, "target": 100, "weight": "60", "polarity": "Positive"},
			{"kpi": "Complaints", "uom": UOM, "target": 5, "weight": "40", "polarity": "Negative"},
		]
		asked = {
			"reviewee": ANN,
			"reviewee_name": "Ann",
			"form_reference": questionnaire,
			"docstatus": 1,
			**period,
		}
		return {
			"Employee": {name: {"employee_number": name} for name in (ANN, BEN, BOSS)},
			"KPI UOM": {UOM: {"name1": UOM}},
			"PMS Question Trait": {TRAIT: {"question_trait": TRAIT}},
			"PMS Question": {
				"QTN-00001": {"question": QUESTION, "is_a_general_question": 1, "question_head": "Non KPI"}
			},
			"PMS Settings": {
				"PMS Settings": {
					"overall_kpi_weight": 70,
					"overall__360_weight": 30,
					"kpi_score": [{"score": "0-50", "remark": "Below"}, {"score": "51-100", "remark": "Met"}],
					"overall_score": [
						{"score": "0-59", "remark": "Needs work"},
						{"score": "60-100", "remark": "Strong"},
					],
					"increments": [{"score": "60-100", "status": "Increment", "increment_": "10"}],
					"pms__channel": [{"channel": "_No Such Channel", "hrbps": BOSS}],
				}
			},
			"PMS Employee Relationship": {
				ANN: {
					"employee": ANN,
					"is_locked": 1,
					"peers": [{"employee": BEN}, {"employee": "HR-EMP-GONE"}],
				}
			},
			"KPI Template": {f"KPI-T|01-{cls.fiscal_year}|{ANN}|SYSTEM": {**kpi, "items": rows}},
			"KPI Result": {
				f"KPI-R|01-{cls.fiscal_year}|{ANN}|{BOSS}": {
					**kpi,
					"kpi_template": f"KPI-T|01-{cls.fiscal_year}|{ANN}|SYSTEM",
					"overall_score": "94.0",
					"items": [{**rows[0], "achieved": 90}, {**rows[1], "achieved": 4}],
				}
			},
			"PMS 360 Degree": {
				f"PMS 360 Degree {cls.fiscal_year}-Q1": {
					**period,
					"departments": [
						{
							"department": cls.department,
							"superior": 1,
							"superior_weight": "60",
							"peers": 1,
							"peers_weight": "40",
						},
						{"department": "_No Such Department - X", "superior": 1, "superior_weight": "60"},
					],
				}
			},
			"PMS Questionnaire": {
				questionnaire: {
					"employee": ANN,
					"employee_name": "Ann",
					"department": cls.department,
					"status": "Completed",
					"pms_questionnaire_list": [
						{"question": QUESTION, "question_trait": TRAIT, "question_head": "Non KPI"}
					],
					**period,
				}
			},
			"PMS Form Allocation": {
				by_boss: {**asked, "reviewer": BOSS, "relationship_type": "Line Manager"},
				by_ben: {**asked, "reviewer": BEN, "relationship_type": "Peers"},
			},
			"PMS Question Form": {
				"PMS-QF-1": {
					"pms_form_allocation": by_boss,
					"reviewer": BOSS,
					"reviewee": ANN,
					"reviewee_name": "Ann",
					"fiscal_year": cls.fiscal_year,
					"relationship_type": "Line Manager",
					"review_date": "2031-04-02",
					"average_rating": 4.5,
					"rating_score": 54,
					"superior_weight": 60,
					"peers_weight": 40,
					"docstatus": 1,
					"pms_questionnaire_list": [{"question": QUESTION, "rating": 4.5}],
				}
			},
			"PMS Score Sheet": {
				"PMS-SS-1": {
					"employee": ANN,
					"pms_questionnaire": questionnaire,
					"calculated_score": 92.8,
					"increment": 10,
					"old_ctc": 1000,
					"new_ctc": 1100,
					"ctc_impact": 100,
					"docstatus": 1,
				}
			},
		}

	def migrate(self, migrator_class, status: str = "Success"):
		"""Migrate every record of the DocType on the simulated site; all must end with `status`."""
		migrator = migrator_class(self.company)
		results = [migrator.migrate(name) for name in self.site.records[migrator_class.doctype]]
		self.assertEqual({r.status for r in results}, {status}, [r.error for r in results])
		return results

	def note_of(self, result) -> str:
		return frappe.db.get_value("CentHR API Logger", result.log, "error") or ""

	def test_the_twelve_tabs_in_order(self):
		ann = self.ann.name
		period = {"fiscal_year": self.fiscal_year, "quarter": "Q1"}

		# Masters and settings
		for migrator_class in (KpiUomMigrator, PmsQuestionTraitMigrator, PmsQuestionMigrator):
			self.migrate(migrator_class)
		self.assertTrue(frappe.db.exists("PMS Question", {"question": QUESTION}))
		(settings,) = self.migrate(PmsSettingsMigrator)
		self.assertEqual(frappe.db.get_value("PMS Settings", self.company, "overall_kpi_weight"), 70)
		self.assertIn("_No Such Channel", self.note_of(settings))

		# Peer mapping: the peer who is not here is left out, the lock is kept
		(mapping,) = self.migrate(PmsEmployeeRelationshipMigrator)
		doc = frappe.get_doc("PMS Employee Relationship", ann)
		self.assertEqual(([row.employee for row in doc.peers], doc.locked), ([self.ben.name], 1))
		self.assertIn("HR-EMP-GONE", self.note_of(mapping))
		self.assertFalse(frappe.db.exists("PMS Employee Relationship", self.ben.name))

		# KPI: the submitted template does not make a result; the result is migrated and scored again
		self.migrate(KpiTemplateMigrator)
		template = frappe.db.get_value("KPI Template", {"employee": ann, "month": "Jan", "docstatus": 1})
		self.assertEqual(template, f"KPI-T|01-{self.fiscal_year}|{ann}")
		self.assertFalse(frappe.db.exists("KPI Result", {"employee": ann}))
		self.migrate(KpiResultMigrator)
		result = frappe.db.get_value(
			"KPI Result",
			{"employee": ann},
			["kpi_template", "overall_score", "remark", "docstatus"],
			as_dict=True,
		)
		self.assertEqual(
			(result.kpi_template, result.overall_score, result.remark, result.docstatus),
			(template, 94, "Met", 1),
		)

		# 360 review: only this company's department is kept
		(setup,) = self.migrate(Pms360DegreeMigrator)
		departments = frappe.get_doc("PMS 360 Degree", {"company": self.company, **period}).departments
		self.assertEqual(
			[(row.department, row.superior_weight, row.peers_weight) for row in departments],
			[(self.department, 60, 40)],
		)
		self.assertIn("_No Such Department", self.note_of(setup))
		self.migrate(PmsQuestionnaireMigrator)
		questionnaire = frappe.get_doc("PMS Questionnaire", {"employee": ann, **period})
		self.assertEqual(
			(questionnaire.status, [row.question for row in questionnaire.pms_questionnaire_list]),
			("Completed", [QUESTION]),
		)

		# The reviews asked for, then the one that was given
		self.migrate(PmsFormAllocationMigrator)
		asked = frappe.get_all(
			"PMS Form Allocation", filters={"reviewee": ann, "docstatus": 1}, fields=["reviewer", "status"]
		)
		self.assertCountEqual(
			[(a.reviewer, a.status) for a in asked], [(self.boss.name, "Pending"), (self.ben.name, "Pending")]
		)
		self.migrate(PmsQuestionFormMigrator)
		review = frappe.get_doc("PMS Question Form", {"reviewee": ann})
		self.assertEqual(
			(review.reviewer, review.rating_score, review.quarter, review.docstatus),
			(self.boss.name, 54, "Q1", 1),
		)
		self.assertEqual(
			frappe.db.get_value("PMS Form Allocation", review.pms_form_allocation, "status"), "Completed"
		)

		# The scores CentHR shows are made of the migrated records: KPI 94 at 70% and 360 score 90 at 30%
		rows = OverallScores(self.fiscal_year, quarter="Q1", department=self.department).get_rows()
		row = next(r for r in rows if r["employee"] == ann)
		self.assertEqual((row["kpi_score"], row["review_score"], row["overall_score"]), (94, 90, 92.8))
		self.assertEqual((row["reviews_done"], row["reviews_total"]), (1, 2))

		# The score sheet keeps what was decided
		self.migrate(PmsScoreSheetMigrator)
		sheet = frappe.get_doc("PMS Score Sheet", {"employee": ann, **period})
		self.assertEqual(
			(sheet.status, sheet.docstatus, sheet.outcome, sheet.new_ctc), ("Approved", 1, "Increment", 1100)
		)

		# A second run creates nothing
		for migrator_class in (
			KpiUomMigrator,
			PmsSettingsMigrator,
			KpiTemplateMigrator,
			KpiResultMigrator,
			PmsQuestionFormMigrator,
			PmsScoreSheetMigrator,
		):
			self.migrate(migrator_class, status="Already Exists")
		fetched = KpiTemplateMigrator(self.company).fetch({})
		self.assertEqual([row["migration_status"] for row in fetched], ["Success"])

	def test_a_result_waits_for_its_template(self):
		migrator = KpiResultMigrator(self.company)
		name = next(iter(self.site.records["KPI Result"]))
		with patch("centhr.api.migrate.kpi_result.find_local", return_value=None):
			result = migrator.migrate(name)

		self.assertEqual(result.status, "Failed")
		self.assertIn("KPI Template tab first", result.error)
