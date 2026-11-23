# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

from unittest.mock import patch
from urllib.parse import unquote

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api.common.pms_sync import PmsSync, delete_pms_record, enqueue_pms_job, get_pms_targets
from centhr.api.common.target_client import TargetClient
from centhr.api.delete.pms import enqueue_pms_delete
from centhr.api.post.employee import get_field_values
from centhr.pms.testing import (
	get_fiscal_year_2031,
	make_department,
	make_employee,
	make_settings,
	make_uom,
	submit_kpi_result,
)

# The IDs the employees have on the company site
ANN, BEN, BOSS = "SITE-EMP-ANN", "SITE-EMP-BEN", "SITE-EMP-BOSS"
SITE_DEPARTMENT = "Sales - SITE"


class FakeTarget(frappe._dict):
	def get_password(self, fieldname):
		return "secret"


class FakeSite:
	"""A company site: keeps what is sent to it and answers lists from that. Like the real one, it
	names a new record itself, and a KPI Template submitted there makes a draft KPI Result."""

	def __init__(self, records: dict[str, list[dict]]):
		self.records = records
		self.calls = []

	def __call__(self, method, url, **kwargs):
		doctype, _, name = unquote(url.rsplit("/api/resource/", 1)[1]).partition("/")
		self.calls.append(frappe._dict(method=method, doctype=doctype, name=name, json=kwargs.get("json")))
		rows = self.records.setdefault(doctype, [])
		if method == "GET":
			filters = frappe.parse_json(kwargs["params"]["filters"])
			or_filters = frappe.parse_json(kwargs["params"].get("or_filters") or "[]")
			found = [row for row in rows if all(matches(row, f) for f in filters)]
			if or_filters:
				found = [row for row in found if any(matches(row, f) for f in or_filters)]
			return [{"docstatus": 0, **row} for row in found]
		if method == "POST":
			record = {"name": f"SITE-{doctype}-{len(rows) + 1}", **kwargs["json"]}
			rows.append(record)
		elif method == "PUT":
			record = next((row for row in rows if row["name"] == name), None)
			if record is None:
				# A single, such as PMS Settings, is there from the start
				record = {"name": name}
				rows.append(record)
			record.update(kwargs["json"])
		else:
			rows[:] = [row for row in rows if row["name"] != name]
			return None
		self.make_result_of(doctype, record)
		return record

	def make_result_of(self, doctype: str, template: dict) -> None:
		results = self.records.setdefault("KPI Result", [])
		period = {key: template.get(key) for key in ("employee", "fiscal_year", "month")}
		made = any(all(row.get(k) == v for k, v in period.items()) for row in results)
		if doctype == "KPI Template" and template.get("docstatus") == 1 and not made:
			results.append({"name": "SITE-RESULT-MADE-THERE", "docstatus": 0, **period})

	def writes(self, doctype: str) -> list[tuple]:
		return [(c.method, c.name) for c in self.calls if c.method != "GET" and c.doctype == doctype]


def matches(row: dict, condition: list) -> bool:
	fieldname, operator, value = condition
	if operator == "is":
		return not row.get(fieldname)
	if operator == "!=":
		return row.get(fieldname, 0) != value
	return row.get(fieldname) == value


class TestPmsSync(IntegrationTestCase):
	"""PMS records made here against a simulated company site; nothing leaves this site."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		cls.addClassCleanup(frappe.clear_document_cache, "PMS Settings", cls.company)
		cls.fiscal_year = get_fiscal_year_2031()
		make_settings(cls.company)
		make_uom()
		cls.department = make_department(cls.company, "_Test PMS Sync Sales")
		cls.boss = cls.make_staff("SyncBoss", BOSS)
		cls.ann = cls.make_staff("SyncAnn", ANN, cls.boss.name)
		cls.ben = cls.make_staff("SyncBen", BEN, cls.boss.name)
		cls.target = FakeTarget(company=cls.company, base_url="http://site.test/", api_key="key", sync_pms=1)

	@classmethod
	def make_staff(cls, name: str, site_id: str, reports_to: str | None = None):
		employee = make_employee(cls.company, name, cls.department, reports_to, roles=None)
		# The Employee sync sends this as the employee's number on the company site
		employee.db_set("employee_number", f"NUMBER-{site_id}")
		return employee

	def setUp(self):
		self.site = FakeSite(
			{
				"Employee": [{"name": n, "employee_number": f"NUMBER-{n}"} for n in (ANN, BEN, BOSS)],
				"Department": [
					{
						"name": SITE_DEPARTMENT,
						"department_name": "_Test PMS Sync Sales",
						"company": self.company,
					}
				],
			}
		)
		patcher = patch.object(
			TargetClient, "request", lambda client, method, url, **kw: self.site(method, url, **kw)
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def send(self, doc) -> None:
		PmsSync(self.target, doc).upsert()

	def on_site(self, doctype: str) -> list[dict]:
		return self.site.records.get(doctype, [])

	def test_result_brings_its_template_and_takes_the_one_made_there(self):
		result = submit_kpi_result(self.ann.name, self.fiscal_year, "Mar", (90, 4))

		self.send(result)

		(template,) = self.on_site("KPI Template")
		self.assertEqual(
			(template["employee"], template["department"], template["docstatus"]), (ANN, SITE_DEPARTMENT, 1)
		)
		self.assertNotIn("company", template)
		# The site made a draft result when the template was submitted; that one is filled in, not a second
		(sent,) = self.on_site("KPI Result")
		self.assertEqual(
			(sent["name"], sent["kpi_template"], sent["docstatus"]),
			("SITE-RESULT-MADE-THERE", template["name"], 1),
		)
		self.assertEqual([row["achieved"] for row in sent["items"]], [90, 4])
		self.assertEqual(self.site.writes("KPI Result"), [("PUT", "SITE-RESULT-MADE-THERE")])

		# Sent again, a submitted record is left alone; cancelled here, it is cancelled there
		self.send(result)
		self.assertEqual(len(self.site.writes("KPI Result")), 1)
		result.docstatus = 2
		self.send(result)
		self.assertEqual(self.on_site("KPI Result")[0]["docstatus"], 2)

	def test_peer_mapping_is_sent_in_the_sites_own_terms(self):
		mapping = frappe.get_doc(
			{
				"doctype": "PMS Employee Relationship",
				"employee": self.ann.name,
				"peers": [{"employee": self.ben.name}],
			}
		).insert()
		mapping.locked = 1

		self.send(mapping)
		self.send(mapping)

		(sent,) = self.on_site("PMS Employee Relationship")
		self.assertEqual((sent["employee"], sent["line_manager"], sent["is_locked"]), (ANN, BOSS, 1))
		self.assertEqual([row["employee"] for row in sent["peers"]], [BEN])
		self.assertNotIn("locked", sent)
		# The second time it is the same record, found by its employee
		self.assertEqual(
			[method for method, _name in self.site.writes("PMS Employee Relationship")], ["POST", "PUT"]
		)

	def test_settings_and_masters(self):
		uom = frappe.get_all("KPI UOM", pluck="name", limit=1)[0]

		self.send(frappe.get_doc("PMS Settings", self.company))
		self.send(frappe.get_doc("KPI UOM", uom))

		# The site has one PMS Settings, so it is always an update of that one
		(settings,) = self.on_site("PMS Settings")
		self.assertEqual(self.site.writes("PMS Settings"), [("PUT", "PMS Settings")])
		self.assertEqual(settings["overall_kpi_weight"], 70)
		self.assertNotIn("company", settings)
		# A master keeps its name
		self.assertEqual([row["name"] for row in self.on_site("KPI UOM")], [uom])

	def test_delete_finds_the_record_by_what_it_was_about(self):
		template = frappe.get_doc(
			{
				"doctype": "KPI Template",
				"employee": self.ben.name,
				"fiscal_year": self.fiscal_year,
				"month": "Apr",
				"items": [
					{
						"kpi": "Calls",
						"uom": frappe.get_all("KPI UOM", pluck="name", limit=1)[0],
						"target": 10,
						"weight": "100",
						"polarity": "Positive",
					}
				],
			}
		).insert()
		self.send(template)
		self.assertEqual(len(self.on_site("KPI Template")), 1)
		values = frappe.parse_json(frappe.as_json(get_field_values(template)))

		with patch("centhr.api.common.pms_sync.get_pms_targets", return_value=[self.target]):
			delete_pms_record("KPI Template", template.name, self.company, values)

		self.assertEqual(self.on_site("KPI Template"), [])

	def test_only_sites_that_ask_get_pms_records(self):
		rows = [
			FakeTarget(company=self.company, base_url="http://a.test", api_key="a", sync_pms=0),
			FakeTarget(company=self.company, base_url="http://b.test", api_key="b", sync_pms=1),
		]
		template = frappe.new_doc("KPI Template").update({"employee": self.ann.name, "company": self.company})

		with (
			patch("centhr.api.common.pms_sync.get_targets", return_value=rows),
			patch("centhr.api.common.pms_sync.frappe.enqueue") as enqueue,
		):
			self.assertEqual([t.base_url for t in get_pms_targets(self.company)], ["http://b.test"])
			enqueue_pms_delete(template)
			self.assertEqual(enqueue.call_count, 1)
			# A record that came in by the migration tool is not sent back
			frappe.flags.centhr_migration = True
			self.addCleanup(frappe.flags.pop, "centhr_migration", None)
			enqueue_pms_job("centhr.api.post.pms.sync_pms", template, doctype="KPI Template", name="X")
			self.assertEqual(enqueue.call_count, 1)

		with (
			patch("centhr.api.common.pms_sync.get_targets", return_value=rows[:1]),
			patch("centhr.api.common.pms_sync.frappe.enqueue") as enqueue,
		):
			enqueue_pms_delete(template)
			enqueue.assert_not_called()
