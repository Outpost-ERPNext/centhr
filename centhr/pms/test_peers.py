import frappe
from frappe.tests import IntegrationTestCase

from centhr.pms.peers import MAPPING, PeerMapping
from centhr.pms.testing import make_department, make_employee, make_settings

JUNIOR, SENIOR = "_Test PMS Junior", "_Test PMS Senior"


def peers_of(employee) -> list[str]:
	return [row.employee for row in frappe.get_doc(MAPPING, employee.name).peers]


class TestPeerMapping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		cls.addClassCleanup(frappe.clear_document_cache, "PMS Settings", cls.company)
		for grade in (JUNIOR, SENIOR):
			frappe.get_doc({"doctype": "Employee Grade", "name": grade}).insert()
		make_settings(cls.company)
		settings = frappe.get_doc("PMS Settings", cls.company)
		settings.set("grade_levels", [{"grade": JUNIOR}, {"grade": SENIOR}])
		settings.save()

	def make_team(self, name: str):
		"""A department whose employees are made in the order given, so their IDs sort the same way."""
		department = make_department(self.company, f"_Test PMS {name}")

		def member(first_name, grade=SENIOR, reports_to=None):
			return make_employee(
				self.company, f"{name}{first_name}", department, reports_to and reports_to.name, None, grade
			)

		return member

	def run_mapping(self) -> dict:
		return PeerMapping(self.company).run()

	def test_closest_colleagues_come_first(self):
		member = self.make_team("Sales")
		boss, other_boss = member("Boss"), member("OtherBoss")
		far = member("Far", reports_to=other_boss)
		ann, ben, cal = (member(n, reports_to=boss) for n in ("Ann", "Ben", "Cal"))

		self.run_mapping()

		# Same grade and line manager beat the same grade under another manager, although Far comes first
		self.assertEqual(peers_of(ann), [ben.name, cal.name])
		# Nobody else reports to Far's manager, so the same grade is enough; the manager is never a peer
		self.assertNotIn(other_boss.name, peers_of(far))
		self.assertEqual(len(peers_of(far)), 2)

	def test_one_grade_lower_fills_the_free_places(self):
		member = self.make_team("Ops")
		lead = member("Lead")
		junior_one, junior_two = member("JuniorOne", JUNIOR), member("JuniorTwo", JUNIOR)

		self.run_mapping()

		self.assertEqual(peers_of(lead), [junior_one.name, junior_two.name])
		# There is no grade below Junior, and a senior is not a junior's peer
		self.assertEqual(peers_of(junior_one), [junior_two.name])

	def test_peers_who_left_are_replaced_and_locked_mappings_are_kept(self):
		member = self.make_team("Tech")
		ann, ben, cal, dan = (member(n) for n in ("Ann", "Ben", "Cal", "Dan"))
		self.run_mapping()
		self.assertEqual(peers_of(ann), [ben.name, cal.name])
		self.assertEqual(peers_of(dan), [ann.name, ben.name])

		frappe.get_doc(MAPPING, ann.name).set_lock(True)
		frappe.db.set_value("Employee", ben.name, "status", "Left")
		stats = self.run_mapping()

		self.assertEqual(peers_of(ann), [ben.name, cal.name])
		self.assertEqual(peers_of(dan), [ann.name, cal.name])
		self.assertGreaterEqual(stats.locked, 1)

	def test_a_second_run_changes_nothing(self):
		member = self.make_team("Calm")
		for name in ("Ann", "Ben", "Cal"):
			member(name)
		self.run_mapping()

		stats = self.run_mapping()

		self.assertEqual((stats.created, stats.peers_added, stats.peers_removed), (0, 0, 0))

	def test_hr_choice_is_mirrored_on_the_peer(self):
		member = self.make_team("HR")
		ann, ben = member("Ann"), member("Ben")

		frappe.get_doc({"doctype": MAPPING, "employee": ann.name, "peers": [{"employee": ben.name}]}).insert()

		self.assertEqual(peers_of(ben), [ann.name])
		self.assertEqual(frappe.db.get_value(MAPPING, ann.name, "peer_names"), ben.employee_name)

	def test_peers_are_checked(self):
		member = self.make_team("Rules")
		boss = member("Boss")
		ann = member("Ann", reports_to=boss)
		others = [member(n) for n in ("Ben", "Cal", "Dan")]
		other_company = frappe.get_all(
			"Company", filters={"name": ["!=", self.company]}, pluck="name", limit=1
		)[0]
		outsider = make_employee(other_company, "RulesOutsider", None, roles=None)

		def mapping_with(*peers):
			return frappe.get_doc(
				{"doctype": MAPPING, "employee": ann.name, "peers": [{"employee": p.name} for p in peers]}
			)

		for peers in ([ann], [boss], others, [others[0], others[0]], [outsider]):
			with self.assertRaises(frappe.ValidationError, msg=[p.employee_name for p in peers]):
				mapping_with(*peers).insert()

		mapping_with(*others[:2]).insert()

	def test_locked_mapping_cannot_be_edited(self):
		member = self.make_team("Lock")
		ann, ben, cal = (member(n) for n in ("Ann", "Ben", "Cal"))
		mapping = frappe.get_doc(
			{"doctype": MAPPING, "employee": ann.name, "peers": [{"employee": ben.name}]}
		).insert()
		mapping.set_lock(True)

		mapping.append("peers", {"employee": cal.name})
		with self.assertRaises(frappe.ValidationError):
			mapping.save()

		mapping.reload()
		mapping.set_lock(False)
		mapping.append("peers", {"employee": cal.name})
		mapping.save()
		self.assertEqual(peers_of(ann), [ben.name, cal.name])
