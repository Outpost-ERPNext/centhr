from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from centhr.api import attendance
from centhr.api.employee import get_quick_view
from centhr.api.payroll import get_payroll_runs
from centhr.api.payroll_run import PayrollGenerator, PayrollRun
from centhr.customization.payroll import validate_line_manager
from centhr.payroll_dashboard import (
	advances,
	analytics,
	audit,
	auto_attendance,
	compliance,
	master_sheet,
	payment_request,
	processing,
	reconcile,
	reminders,
	reports,
	settings,
)
from centhr.payroll_dashboard.scope import Scope
from centhr.pms.testing import get_fiscal_year_2031, make_department, make_employee, make_user

# Everything is created in the test transaction and rolled back with it
START, END = "2031-03-01", "2031-03-31"
COMPONENT = "_Test CentHR Basic"
STRUCTURE = "_Test CentHR Structure"
BASE = 1000


class PayrollTestCase(IntegrationTestCase):
	"""A company that can run payroll, with three paid employees and one who left in the cycle."""

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
		cls.bank = frappe.db.get_value(
			"Account", {"company": cls.company, "account_type": ["in", ["Bank", "Cash"]], "is_group": 0}
		)


class TestPayrollRun(PayrollTestCase):
	"""A whole payroll run through the code the Payroll Dashboard calls."""

	def slips_of(self, entry: str) -> dict[str, frappe._dict]:
		rows = frappe.get_all(
			"Salary Slip",
			filters={"payroll_entry": entry, "docstatus": ["!=", 2]},
			fields=[
				"name",
				"employee",
				"docstatus",
				"status",
				"net_pay",
				"gross_pay",
				"payment_days",
				"journal_entry",
			],
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

		# The payout list names everyone the run pays
		payouts = processing.get_payout_list(regular)
		self.assertEqual((len(payouts["rows"]), payouts["total"]), (3, 3 * BASE))

		self.check_payment_request(regular)
		self.check_obligation(regular)

	def check_payment_request(self, entry: str):
		"""Accounts approves the payment request before the bank entry is made."""
		# A salary on hold is paid later, when it is released
		payable = sum(s.net_pay for s in self.slips_of(entry).values() if s.status != "Withheld")
		self.assertEqual(PayrollRun(entry).summary()["next_step"], "payment_request")
		with self.assertRaisesRegex(frappe.ValidationError, "approved"):
			PayrollRun(entry).run_step("bank_entry", self.bank)

		PayrollRun(entry).run_step("payment_request", self.bank)
		summary = PayrollRun(entry).summary()
		request = summary["payment_request"]
		self.assertEqual(
			(summary["next_step"], request["status"], request["amount"]), (None, "Pending Approval", payable)
		)
		# One request per entry
		with self.assertRaises(frappe.ValidationError):
			PayrollRun(entry).run_step("payment_request", self.bank)

		payment_request.decide(request["name"], approve=True)
		self.assertEqual(PayrollRun(entry).summary()["next_step"], "bank_entry")
		PayrollRun(entry).run_step("bank_entry", self.bank)
		summary = PayrollRun(entry).summary()
		self.assertIsNone(summary["next_step"])
		bank_entry = frappe.get_doc("Journal Entry", summary["payment_request"]["journal_entry"])

		# Paid once Accounts submits the bank entry
		bank_entry.update({"cheque_no": "TEST-1", "cheque_date": END})
		bank_entry.submit()
		self.assertEqual(PayrollRun(entry).summary()["payment_request"]["status"], "Paid")

	def check_obligation(self, entry: str):
		"""An obligation's liability is explained per employee, and paid through a request too."""
		account = frappe.db.get_value(
			"Salary Component Account", {"parent": COMPONENT, "company": self.company}, "account"
		)
		obligation = frappe.get_doc(
			{
				"doctype": "Statutory Obligation",
				"obligation_name": "_Test CentHR Levy",
				"company": self.company,
				"liability_account": account,
				"frequency": "Monthly",
				"due_day": 10,
			}
		).insert()

		breakdown = compliance.ObligationBreakdown(obligation.name, self.scope).run()
		self.assertEqual(breakdown["components"], [COMPONENT])
		self.assertEqual({row["employee"] for row in breakdown["rows"]}, {e.name for e in self.staff})
		self.assertEqual(breakdown["total"], 3 * BASE)
		self.assertEqual(breakdown["total"] + breakdown["difference"], breakdown["payable"])

		request = compliance.request_payment(obligation.name, 500, self.bank)
		with self.assertRaises(frappe.ValidationError):
			compliance.request_payment(obligation.name, 100, self.bank)
		self.assertEqual(compliance.get_compliance(self.scope)["obligations"][-1]["open_request"], request)
		with self.assertRaisesRegex(frappe.ValidationError, "why"):
			payment_request.decide(request, approve=False)
		payment_request.decide(request, approve=True)
		# Approval makes the draft bank entry that Accounts submits
		entry = frappe.db.get_value("Payment Request Form", request, "journal_entry")
		self.assertEqual(frappe.db.get_value("Journal Entry", entry, ["docstatus", "total_debit"]), (0, 500))

	def test_failed_run_is_retried_and_cancelled_with_its_slips_and_accrual(self):
		april = ("2031-04-01", "2031-04-30")
		entry = PayrollGenerator(self.company, *april, "Regular").run()
		# As after a background job that died: no slips, and the entry says Failed
		for slip in self.slips_of(entry).values():
			frappe.delete_doc("Salary Slip", slip.name, force=True)
		frappe.db.set_value(
			"Payroll Entry",
			entry,
			{"status": "Failed", "salary_slips_created": 0, "error_message": "Worker died"},
		)

		summary = PayrollRun(entry).summary()
		self.assertEqual((summary["next_step"], summary["error_message"]), ("create_slips", "Worker died"))
		PayrollRun(entry).run_step("create_slips")
		self.assertEqual(len(self.slips_of(entry)), 3)

		PayrollRun(entry).run_step("submit_slips")
		journals = {slip.journal_entry for slip in self.slips_of(entry).values()}
		PayrollRun(entry).run_step("payment_request", self.bank)
		PayrollRun(entry).run_step("cancel")

		# Nothing of the run is left: no slips, no accrual, no open payment request
		self.assertEqual(self.slips_of(entry), {})
		self.assertEqual(
			set(frappe.get_all("Journal Entry", filters={"name": ["in", list(journals)]}, pluck="docstatus")),
			{2},
		)
		self.assertEqual(
			frappe.db.get_value("Payment Request Form", {"payroll_entry": entry}, "status"), "Rejected"
		)

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


class TestPayrollAudit(PayrollTestCase):
	def audit_row(self, employee: str, scope: Scope | None = None):
		rows = audit.PayrollAudit(scope or self.scope).run()["rows"]
		return next(row for row in rows if row.name == employee)

	def test_missing_and_inactive_structures_are_separate_checks(self):
		unassigned = make_employee(self.company, "PayNoStructure", None, roles=None)
		frappe.db.set_value("Salary Structure", STRUCTURE, "is_active", "No")
		self.addCleanup(frappe.db.set_value, "Salary Structure", STRUCTURE, "is_active", "Yes")

		missing = self.audit_row(unassigned.name).issues
		inactive = self.audit_row(self.staff[0].name).issues

		self.assertIn("structure_missing", missing)
		self.assertNotIn("structure_inactive", missing)
		self.assertIn("structure_inactive", inactive)
		self.assertNotIn("structure_missing", inactive)

	def test_each_missing_dimension_is_named(self):
		loner = make_employee(self.company, "PayNoDepartment", None, roles=None)
		ann = self.staff[0].name

		with patch.object(audit, "uses_channels", return_value=True):
			self.assertEqual(
				self.audit_row(loner.name).issues["dimensions"],
				"Missing: department, channel, payroll cost center",
			)
			self.assertEqual(
				self.audit_row(ann).issues["dimensions"], "Missing: channel, payroll cost center"
			)
		with patch.object(audit, "uses_channels", return_value=False):
			self.assertEqual(self.audit_row(ann).issues["dimensions"], "Missing: payroll cost center")
			cost_center = frappe.db.get_value("Cost Center", {"company": self.company, "is_group": 0})
			frappe.db.set_value("Employee", ann, "payroll_cost_center", cost_center)
			self.assertNotIn("dimensions", self.audit_row(ann).issues)

	def test_days_in_an_open_request_are_not_unmarked(self):
		ann = self.staff[0].name
		request = frappe.new_doc("Attendance Request").update(
			{"employee": ann, "company": self.company, "from_date": "2031-03-03", "to_date": "2031-03-04"}
		)
		# Only the dates matter here; HRMS would refuse a request this far ahead
		request.flags.ignore_validate = request.flags.ignore_mandatory = True
		request.insert()

		with patch("centhr.payroll_dashboard.attendance.today", return_value="2031-03-10"):
			row = self.audit_row(ann)

		self.assertEqual((row.attendance["unmarked"], row.attendance["pending_request"]), (8, 2))
		self.assertEqual(row.issues["attendance"], "8 unmarked, 2 in open attendance requests")

	def test_only_negative_drafts_are_deleted(self):
		slips = [
			frappe._dict(name="NEGATIVE-DRAFT", docstatus=0, net_pay=-5),
			frappe._dict(name="ZERO-DRAFT", docstatus=0, net_pay=0),
			frappe._dict(name="NEGATIVE-SUBMITTED", docstatus=1, net_pay=-5),
		]

		with (
			patch.object(Scope, "get_slips", return_value=slips),
			patch.object(processing, "update_slips", return_value={"done": [], "failed": []}) as update,
		):
			processing.delete_negative_slips(self.scope)

		update.assert_called_once_with("delete", ["NEGATIVE-DRAFT"])

	def test_hold_covers_its_cycles_and_is_released_in_bulk(self):
		cal = self.staff[2].name
		april, may, june = (
			Scope.make(f"2031-0{m}-01", f"2031-0{m}-{d}", self.company)
			for m, d in ((4, 30), (5, 31), (6, 30))
		)

		hold = audit.set_hold(cal, april, "Exit clearance pending", cycles=2)

		row = self.audit_row(cal, may)
		self.assertEqual((row.hold, row.hold_cycles, row.hold_until_released), (hold, 2, False))
		self.assertIsNone(self.audit_row(cal, june).hold)

		outcome = audit.release_holds([hold, "NO-SUCH-HOLD"])
		self.assertEqual((outcome["done"], len(outcome["failed"])), ([hold], 1))
		self.assertIsNone(self.audit_row(cal, may).hold)
		# Without a number of cycles it is held until someone releases it
		audit.set_hold(cal, april, "Under investigation", cycles=0)
		self.assertTrue(self.audit_row(cal, june).hold_until_released)


class TestConfidentialPayroll(PayrollTestCase):
	"""Employees on a confidential salary structure are paid in their own batch and hidden from
	users without the structure's role."""

	EXECUTIVE = "_Test CentHR Executive"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		structure = frappe.copy_doc(frappe.get_doc("Salary Structure", STRUCTURE))
		structure.name = cls.EXECUTIVE
		structure.insert().submit()
		cls.executive = make_paid_employee(
			cls.company, "PayExec", cls.staff[0].department, cls.payable, cls.EXECUTIVE
		)
		frappe.get_doc(
			{
				"doctype": "Payroll Structure Rule",
				"salary_structure": cls.EXECUTIVE,
				"confidential": 1,
				"allowed_role": "Accounts Manager",
				"batch_name": "Executive",
			}
		).insert()
		# Runs payroll, but is not let in on the executives' salaries
		cls.hr_user = make_user("payroll-hr-manager", ["HR Manager"])

	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")

	def test_confidential_batch_is_paid_apart_and_hidden(self):
		regular = PayrollGenerator(self.company, START, END, "Regular").run()
		executive = PayrollGenerator(self.company, START, END, "Executive").run()
		paid_by = dict(
			frappe.get_all(
				"Salary Slip",
				filters={"payroll_entry": ["in", [regular, executive]]},
				fields=["employee", "payroll_entry"],
				as_list=True,
			)
		)

		self.assertEqual(paid_by[self.executive.name], executive)
		self.assertEqual({paid_by[e.name] for e in self.staff}, {regular})

		frappe.set_user(self.hr_user)
		self.assertNotIn(self.executive.name, [row["name"] for row in self.scope.get_employees()])
		self.assertNotIn(self.executive.name, [slip.employee for slip in self.scope.get_slips()])
		self.assertEqual([run["name"] for run in get_payroll_runs(START, END, self.company)], [regular])
		slip = frappe.db.get_value(
			"Salary Slip", {"employee": self.executive.name, "payroll_entry": executive}
		)
		self.assertFalse(frappe.has_permission("Salary Slip", "read", doc=slip))
		with self.assertRaises(frappe.PermissionError):
			PayrollGenerator(self.company, "2031-04-01", "2031-04-30", "Executive")

	def test_rule_needs_a_role_and_its_own_batch_name(self):
		def rule(**values):
			return frappe.get_doc(
				{"doctype": "Payroll Structure Rule", "salary_structure": STRUCTURE, **values}
			)

		with self.assertRaises(frappe.ValidationError):
			rule(confidential=1, batch_name="Executive").insert()
		with self.assertRaises(frappe.ValidationError):
			rule(confidential=1, allowed_role="HR Manager", batch_name="Regular").insert()


class TestPayrollHelpers(PayrollTestCase):
	def test_auto_attendance_marks_only_unmarked_working_days(self):
		frappe.get_doc(
			{"doctype": "Payroll Structure Rule", "salary_structure": STRUCTURE, "auto_attendance": 1}
		).insert()
		ann = self.staff[0].name
		frappe.get_doc(
			{
				"doctype": "Attendance",
				"employee": ann,
				"attendance_date": "2031-03-02",
				"status": "Absent",
				"company": self.company,
			}
		).insert().submit()

		with (
			patch("centhr.payroll_dashboard.attendance.today", return_value="2031-03-05"),
			patch("centhr.payroll_dashboard.auto_attendance.today", return_value="2031-03-05"),
		):
			first = auto_attendance.AutoAttendance(self.scope).run()
			second = auto_attendance.AutoAttendance(self.scope).run()

		# Three staff and the leaver, five days each, less Ann's day that was marked already
		self.assertEqual((first["employees"], first["created"]), (4, 19))
		self.assertEqual(second["created"], 0)
		self.assertEqual(
			frappe.db.get_value("Attendance", {"employee": ann, "attendance_date": "2031-03-02"}, "status"),
			"Absent",
		)

	def test_reminders_go_to_the_employee_and_the_approver(self):
		ann, ben = self.staff[0], self.staff[1]
		manager = make_employee(self.company, "PayManager", ann.department, roles=["HR User"])
		frappe.db.set_value("Employee", ann.name, "personal_email", "ann@pms-test.example")
		frappe.db.set_value("Employee", ben.name, "reports_to", manager.name)
		request = frappe.new_doc("Attendance Request").update(
			{
				"employee": ben.name,
				"company": self.company,
				"from_date": "2031-03-03",
				"to_date": "2031-03-04",
			}
		)
		request.flags.ignore_validate = request.flags.ignore_mandatory = True
		request.insert()

		with (
			patch("centhr.payroll_dashboard.attendance.today", return_value="2031-03-10"),
			patch.object(frappe, "sendmail") as sendmail,
		):
			outcome = reminders.Reminders(self.scope).send([ann.name, ben.name])

		# Ann about her unmarked days (Ben has no email address), the manager about Ben's open request.
		# The date is past the days another test of this class marks automatically
		self.assertEqual(sendmail.call_count, 2)

		self.assertEqual(outcome["recipients"], sorted(["ann@pms-test.example", manager.user_id]))
		sent = reminders.get_last_sent([ann.name, ben.name], self.scope)
		self.assertEqual(set(sent), {ann.name, ben.name})

	def test_advance_quick_view_says_where_recovery_stands(self):
		advance = frappe._dict(
			name="ADV-TEST",
			due_date="2031-02-10",
			paid_amount=100,
			claimed_amount=0,
			return_amount=0,
			repay_unclaimed_amount_from_salary=0,
		)

		self.assertEqual(advances.due_status(advance, self.scope), "Overdue")
		self.assertEqual(
			advances.due_status(frappe._dict(due_date="2031-03-20"), self.scope), "Due this cycle"
		)
		self.assertEqual(advances.due_status(frappe._dict(due_date="2031-05-01"), self.scope), "Upcoming")
		self.assertEqual(advances.due_status(frappe._dict(), self.scope), "No due date")
		self.assertIn("not ticked", advances.recovery_note(advance, [], self.scope))

	def test_custom_reports_show_up_for_those_who_may_open_them(self):
		def make_report(name: str, doctype: str):
			return frappe.get_doc(
				{
					"doctype": "Report",
					"report_name": name,
					"ref_doctype": doctype,
					"report_type": "Report Builder",
					"is_standard": "No",
					"roles": [{"role": "HR Manager"}],
				}
			).insert()

		make_report("_Test CentHR Slip Register", "Salary Slip")
		make_report("_Test CentHR Master Sheets", "Payroll Master Sheet")
		self.addCleanup(frappe.set_user, "Administrator")

		listed = {r["name"]: r["category"] for r in reports.get_reports()}
		self.assertEqual(listed["_Test CentHR Slip Register"], "Payroll")
		self.assertEqual(listed["_Test CentHR Master Sheets"], "Payroll")
		self.assertEqual(reports.categorize("Monthly Headcount"), "HR & Staff")

		# Without the report's role, or the right to report on its DocType, it is not offered
		frappe.set_user(make_user("payroll-no-reports", ["Employee"]))
		self.assertNotIn("_Test CentHR Slip Register", [r["name"] for r in reports.get_reports()])


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

	def test_calculation_rules_are_saved_to_hrms_payroll_settings(self):
		before = settings.get_site_settings()
		self.addCleanup(settings.save_site_settings, before)
		other = "Absent" if before["consider_unmarked_attendance_as"] == "Present" else "Present"

		saved = settings.save_settings(
			self.company, 1, False, {"consider_unmarked_attendance_as": other, "name": "ignored"}
		)

		self.assertEqual(saved["site"]["consider_unmarked_attendance_as"], other)
		self.assertEqual(
			frappe.db.get_single_value("Payroll Settings", "consider_unmarked_attendance_as"), other
		)

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


def make_paid_employee(company: str, name: str, department: str, payable: str, structure: str = STRUCTURE):
	employee = make_employee(company, name, department, roles=None)
	assignment = frappe.get_doc(
		{
			"doctype": "Salary Structure Assignment",
			"employee": employee.name,
			"company": company,
			"salary_structure": structure,
			"from_date": "2031-01-01",
			"base": BASE,
			"currency": frappe.get_cached_value("Company", company, "default_currency"),
			"payroll_payable_account": payable,
		}
	).insert()
	assignment.submit()
	return employee
