from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api import attendance
from centhr.api.employee import get_quick_view
from centhr.api.payroll_run import PayrollGenerator, PayrollRun
from centhr.customization.payroll import validate_line_manager
from centhr.payroll_dashboard import analytics, audit, processing, reconcile, settings
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
		self.assertEqual(get_quick_view(self.staff[0].name, START, END)["salary_slip"]["name"], slip.name)

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
				currency="NGN",
				net_pay=BASE,
				gross_pay=BASE,
				total_deduction=0,
				payment_days=31,
			)
			for i, e in enumerate(self.staff)
		]
		ann, ben, cal = (e.name for e in self.staff)
		sheet = f'Staff ID,Net Pay,Payment Days\n{ann},"1,000.00",31\n{ben},950,31\nGHOST-1,500,31\n'.encode()

		with patch.object(Scope, "get_slips", return_value=slips):
			result = reconcile.reconcile(self.scope, "master.csv", sheet)

		status = {row["employee"]: row["status"] for row in result["rows"]}
		self.assertEqual(
			status, {ann: "Matched", ben: "Discrepancy", cal: "Missing in Excel", "GHOST-1": "Missing in ERP"}
		)
		self.assertEqual(next(r for r in result["rows"] if r["employee"] == ben)["variance"], 50)
		with self.assertRaises(frappe.ValidationError):
			reconcile.reconcile(self.scope, "master.csv", b"Name,Amount\nx,1\n")


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
