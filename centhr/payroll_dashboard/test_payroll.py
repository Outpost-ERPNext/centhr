from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api import attendance
from centhr.api.employee import get_quick_view
from centhr.api.payroll_run import PayrollGenerator, PayrollRun
from centhr.customization.payroll import validate_line_manager
from centhr.payroll_dashboard import analytics, audit, master_sheet, processing, reconcile, settings
from centhr.payroll_dashboard.scope import Scope
from centhr.pms.testing import get_fiscal_year_2031, make_department, make_employee

# Everything is created in the test transaction and rolled back with it
START, END = "2031-03-01", "2031-03-31"
COMPONENT = "_Test CentHR Basic"
STRUCTURE = "_Test CentHR Structure"
BASE = 1000


class TestPayrollRun(IntegrationTestCase):
	"""A whole payroll run through the code the Payroll Dashboard calls."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]
		get_fiscal_year_2031()
		cls.payable = set_up_company(cls.company)
		make_structure(cls.company)
		department = make_department(cls.company, "_Test CentHR Payroll")
		cls.staff = [
			make_paid_employee(cls.company, f"Pay{n}", department, cls.payable) for n in ("Ann", "Ben", "Cal")
		]
		cls.leaver = make_paid_employee(cls.company, "PayLeaver", department, cls.payable)
		frappe.db.set_value("Employee", cls.leaver.name, {"status": "Left", "relieving_date": "2031-03-15"})
		cls.scope = Scope.make(START, END, cls.company)

	def slips_of(self, entry: str) -> dict[str, frappe._dict]:
		rows = frappe.get_all(
			"Salary Slip",
			filters={"payroll_entry": entry, "docstatus": ["!=", 2]},
			fields=["name", "employee", "docstatus", "net_pay", "gross_pay", "payment_days", "journal_entry"],
		)
		return {row.employee: row for row in rows}

	def test_regular_and_exited_batches_then_submit_and_journal(self):
		regular = PayrollGenerator(self.company, START, END, "Regular").run()
		exited = PayrollGenerator(self.company, START, END, "Exited").run()

		# Each batch pays its own employees, once
		self.assertEqual(set(self.slips_of(regular)), {e.name for e in self.staff})
		self.assertEqual(set(self.slips_of(exited)), {self.leaver.name})
		self.assertEqual(PayrollRun(exited).summary()["batch"], "Exited")
		self.assertEqual(self.slips_of(regular)[self.staff[0].name].net_pay, BASE)
		with self.assertRaises(frappe.ValidationError):
			PayrollGenerator(self.company, START, END, "Regular").run()

		# The quick view shows a slip's lines
		slip = self.slips_of(regular)[self.staff[0].name]
		details = processing.get_slip_details(slip.name)
		self.assertEqual(details["earnings"], [{"salary_component": COMPONENT, "amount": BASE}])
		quick_view = get_quick_view(self.staff[0].name, START, END)
		self.assertEqual(quick_view["salary_slip"]["name"], slip.name)
		self.assertEqual(quick_view["payable_account"], self.payable)

		# Before the slips are submitted nothing is booked
		self.assertEqual(PayrollRun(regular).summary()["next_step"], "submit_slips")
		PayrollRun(regular).run_step("submit_slips")
		slips = self.slips_of(regular)
		self.assertTrue(all(s.docstatus == 1 and s.journal_entry for s in slips.values()))

		# The journal summary confirms the run against its accrual journal entry
		summary = analytics.journal_summary(self.scope)
		by_employee = {row["employee"]: row["journal_status"] for row in summary["rows"]}
		self.assertEqual({by_employee[e.name] for e in self.staff}, {"Confirmed"})
		self.assertEqual(summary["summary"]["reconciled"], 3)
		self.assertEqual(summary["summary"]["earnings_variance"], 0)

	def test_hold_needs_a_reason_and_shows_it(self):
		employee = self.staff[1].name
		with self.assertRaises(frappe.ValidationError):
			audit.set_hold(employee, self.scope, "  ")

		audit.set_hold(employee, self.scope, "Disciplinary case open")

		row = next(r for r in audit.PayrollAudit(self.scope).run()["rows"] if r.name == employee)
		self.assertTrue(row.hold)
		self.assertEqual(row.hold_reason, "Disciplinary case open")

	def test_excel_reconciliation(self):
		slips = [
			frappe._dict(
				name=f"SLIP-{i}",
				employee=e.name,
				employee_name=e.employee_name,
				department=e.department,
				currency="NGN",
				net_pay=BASE,
				gross_pay=BASE,
				total_deduction=0,
				payment_days=31,
			)
			for i, e in enumerate(self.staff)
		]
		ann, ben, cal = (e.name for e in self.staff)
		# The rollback after the tests does not take the uploaded file off the disk
		self.addCleanup(master_sheet.remove, self.scope)

		def reconciled(sheet: str) -> dict:
			master_sheet.store(self.scope, "master.csv", sheet.encode())
			with patch.object(Scope, "get_slips", return_value=slips):
				return reconcile.reconcile(self.scope)

		self.assertIsNone(reconcile.reconcile(self.scope)["sheet"])
		# Cal's row and the second ghost's are in the sheet but were never filled in
		result = reconciled(
			f'Staff ID,Net Pay,Payment Days\n{ann},"1,000.00",31\n{ben},950,31\nGHOST-1,500,31\n{cal},,\nGHOST-2,,\n'
		)

		status = {row["employee"]: row["status"] for row in result["rows"]}
		self.assertEqual(
			status, {ann: "Matched", ben: "Discrepancy", cal: "Missing in Excel", "GHOST-1": "Missing in ERP"}
		)
		row = next(r for r in result["rows"] if r["employee"] == ben)
		self.assertEqual((row["variance"], row["differences"]), (50, ["net_pay"]))
		self.assertIn("950", row["remarks"][0])
		self.assertEqual(result["ignored"], 2)
		self.assertEqual((result["summary"]["excel"], result["summary"]["slips"]), (3, 3))
		self.assertEqual(result["sheet"]["file_name"], "master.csv")

		# A new upload replaces the cycle's sheet. One with no net pay at all cannot be compared
		result = reconciled(f"Employee ID,Net Pay\n{ann},\n{ben},\n")
		self.assertIn("Net Pay", result["problem"])
		self.assertEqual(result["rows"], [])
		self.assertEqual(frappe.db.count(master_sheet.DOCTYPE, {"from_date": START}), 1)
		with self.assertRaises(frappe.ValidationError):
			master_sheet.store(self.scope, "master.txt", b"x")

		master_sheet.remove(self.scope)
		self.assertIsNone(reconcile.reconcile(self.scope)["sheet"])

	def test_master_sheet_columns_are_mapped(self):
		"""A sheet with its own headers is compared once HR maps them; the choice is the company's."""
		ann = self.staff[0]
		slip = frappe._dict(
			name="SLIP-MAP",
			employee=ann.name,
			employee_name=ann.employee_name,
			department=ann.department,
			currency="NGN",
			net_pay=BASE,
			gross_pay=BASE,
			total_deduction=0,
			payment_days=31,
		)
		sheet = f"Code,Paid Out,{COMPONENT},Prorated\n{ann.name},₦ 990,400,600\n".encode()
		master_sheet.store(self.scope, "master.csv", sheet)
		self.addCleanup(master_sheet.remove, self.scope)

		def reconciled() -> dict:
			with (
				patch.object(Scope, "get_slips", return_value=[slip]),
				patch.object(reconcile.ComponentAmounts, "get", return_value=600.0),
			):
				return reconcile.reconcile(self.scope)

		self.assertIn("Employee ID, Net Pay", reconciled()["problem"])

		mapping = master_sheet.ColumnMapping(
			self.company, master_sheet.read_stored(master_sheet.get_stored(self.scope)).headers
		)
		# The salary component is recognised by its name
		self.assertEqual(mapping.auto[COMPONENT], COMPONENT)
		with self.assertRaises(frappe.ValidationError):
			mapping.save({"employee": "No Such Column"})
		mapping.save({"employee": "Code", "net_pay": "Paid Out", COMPONENT: "Prorated"})

		row = reconciled()["rows"][0]
		self.assertEqual((row["status"], row["excel_net_pay"], row["variance"]), ("Discrepancy", 990, 10))
		line = next(c for c in row["components"] if c["component"] == COMPONENT)
		self.assertEqual((line["column"], line["excel"], line["differs"]), ("Prorated", 600, False))
		# Only what differs from the recognised columns is kept
		saved = frappe.parse_json(frappe.db.get_value("Company", self.company, master_sheet.MAPPING_FIELD))
		self.assertEqual(saved, {"employee": "Code", "net_pay": "Paid Out", COMPONENT: "Prorated"})


class TestPayrollSettings(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.get_all("Company", pluck="name", order_by="creation asc", limit=1)[0]

	def test_cycle_follows_the_companys_start_day(self):
		settings.save_settings(self.company, 20, False)

		cycle = attendance.get_payroll_cycle(self.company, "2031-07-10")
		years = attendance.get_payroll_years(self.company)

		self.assertEqual((str(cycle["from_date"]), str(cycle["to_date"])), ("2031-06-20", "2031-07-19"))
		self.assertEqual(len(years[0]["periods"]), 12)
		# Day 1 goes back to calendar months, or the company's Payroll Period
		settings.save_settings(self.company, 1, False)
		self.assertEqual(settings.get_start_day(self.company), 0)
		with self.assertRaises(frappe.ValidationError):
			settings.save_settings(self.company, 31, False)

	def test_advance_recovery_needs_the_recovery_component(self):
		frappe.db.set_single_value("CentHr Settings", "iou_salary_component", None)

		with self.assertRaises(frappe.ValidationError):
			settings.save_settings(self.company, 1, True)

	def test_new_employee_names_a_line_manager_or_none(self):
		def new_employee(**values):
			# new_doc marks it as not saved yet, as it is when the form saves it
			return frappe.new_doc("Employee").update({"first_name": "_Test CentHR Line", **values})

		with self.assertRaisesRegex(frappe.ValidationError, "No Line Manager"):
			validate_line_manager(new_employee())

		# Ticking the box is enough, and clears a manager chosen before
		loner = new_employee(custom_no_line_manager=1, reports_to="SOMEONE")
		validate_line_manager(loner)
		self.assertIsNone(loner.reports_to)


def set_up_company(company: str) -> str:
	"""What HRMS needs from the company to pay and book salaries. Returns its payroll payable account."""
	payable = frappe.db.get_value(
		"Company", company, "default_payroll_payable_account"
	) or frappe.db.get_value(
		"Account", {"company": company, "account_type": "Payable", "is_group": 0}, "name"
	)
	holidays = frappe.get_doc(
		{
			"doctype": "Holiday List",
			"holiday_list_name": "_Test CentHR 2031",
			"from_date": "2031-01-01",
			"to_date": "2031-12-31",
		}
	).insert()
	frappe.db.set_value(
		"Company",
		company,
		{"default_payroll_payable_account": payable, "default_holiday_list": holidays.name},
	)
	frappe.clear_document_cache("Company", company)
	return payable


def make_structure(company: str) -> None:
	expense = frappe.db.get_value(
		"Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name"
	)
	frappe.get_doc(
		{
			"doctype": "Salary Component",
			"salary_component": COMPONENT,
			"salary_component_abbr": "_TCB",
			"type": "Earning",
			"accounts": [{"company": company, "account": expense}],
		}
	).insert()
	structure = frappe.get_doc(
		{
			"doctype": "Salary Structure",
			"name": STRUCTURE,
			"company": company,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"payroll_frequency": "Monthly",
			"earnings": [{"salary_component": COMPONENT, "amount_based_on_formula": 1, "formula": "base"}],
		}
	).insert()
	structure.submit()


def make_paid_employee(company: str, name: str, department: str, payable: str):
	employee = make_employee(company, name, department, roles=None)
	assignment = frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"employee": employee.name,
			"company": company,
			"salary_structure": STRUCTURE,
			"from_date": "2031-01-01",
			"base": BASE,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"payroll_payable_account": payable,
		}
	).insert()
	assignment.submit()
	return employee
