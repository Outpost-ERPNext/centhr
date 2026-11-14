# Copyright (c) 2026, Outpost Work LLP and Contributors
# See license.txt

"""IOU Management (SOP/AP/003) end to end: application, approvals, payment, claims, recovery and escalation.

Uses an existing Company with an employee advance account; every record is rolled back after the class.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_to_date, flt, getdate, now_datetime, today

from centhr.iou import actions, advance, claim, routing, scheduler
from centhr.iou.settings import SETTINGS

PREFIX = "_test_iou"


def make_user(key: str, roles: list[str]) -> str:
	email = f"{PREFIX}_{key}@example.com"
	if not frappe.db.exists("User", email):
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": f"IOU {key}", "send_welcome_email": 0}
		)
		user.append_roles(*roles)
		user.insert(ignore_permissions=True)
	return email


class IntegrationTestIOU(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.db.get_value(
			"Company", {"default_employee_advance_account": ["is", "set"]}, "name"
		)
		if not cls.company:
			raise cls.skipTest(cls, "No company with a default employee advance account")
		cls.currency = frappe.get_cached_value("Company", cls.company, "default_currency")
		cls.bank = frappe.db.get_value(
			"Account",
			{"company": cls.company, "account_type": "Bank", "is_group": 0, "disabled": 0, "account_currency": cls.currency},
			"name",
		)
		payable = frappe.db.get_value(
			"Account", {"company": cls.company, "account_type": "Payable", "is_group": 0, "name": ["like", "Creditors%"]}, "name"
		)
		frappe.db.set_value("Company", cls.company, "default_expense_claim_payable_account", payable)
		# HRMS sets advances off against claims only through a Receivable advance account
		receivable = frappe.db.get_value(
			"Account", {"company": cls.company, "account_type": "Receivable", "is_group": 0, "account_currency": cls.currency}, "name"
		)
		frappe.db.set_value("Company", cls.company, "default_employee_advance_account", receivable)
		cls.expense_type = frappe.db.get_value("Expense Claim Account", {"company": cls.company}, "parent")
		if not frappe.db.exists("Email Account", {"default_outgoing": 1, "enable_outgoing": 1}):
			frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": f"{PREFIX} outgoing",
					"email_id": f"{PREFIX}_outgoing@example.com",
					"enable_outgoing": 1,
					"default_outgoing": 1,
					"smtp_server": "localhost",
					"awaiting_password": 1,
				}
			).insert(ignore_permissions=True)

		cls.hod_user = make_user("hod", ["Employee"])
		cls.finance_1 = make_user("finance1", ["Employee", "Accounts User"])
		cls.finance_2 = make_user("finance2", ["Employee", "Accounts Manager"])
		cls.proxy = make_user("proxy", ["Employee"])
		cls.hod = cls.make_employee("hod", cls.hod_user)

		settings = frappe.get_single(SETTINGS)
		settings.iou_finance_1 = cls.finance_1
		settings.iou_finance_2 = cls.finance_2
		settings.iou_proxies = []
		settings.append("iou_proxies", {"approver": cls.hod_user, "proxy": cls.proxy})
		settings.flags.ignore_permissions = True
		settings.save()

	@classmethod
	def make_employee(cls, key: str, user: str | None = None, reports_to: str | None = None) -> str:
		employee = frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": f"{PREFIX} {key}",
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"company": cls.company,
				"status": "Active",
				"user_id": user,
				"reports_to": reports_to,
				"salary_currency": cls.currency,
				"company_email": f"{PREFIX}_{key}_emp@example.com",
			}
		)
		employee.flags.ignore_permissions = True
		# The site makes payroll fields mandatory, which these tests do not use
		employee.flags.ignore_mandatory = True
		employee.insert()
		return employee.name

	def setUp(self):
		frappe.set_user("Administrator")
		self.employee = self.make_employee(frappe.generate_hash(length=6), reports_to=self.hod)

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------ helpers

	def apply(self, amount=100000, purpose_type="Other", tenure=None, employee=None):
		doc = frappe.get_doc(
			{
				"doctype": "Employee Advance",
				"employee": employee or self.employee,
				"company": self.company,
				"currency": self.currency,
				"exchange_rate": 1,
				"posting_date": today(),
				"purpose": "Client visit",
				"advance_amount": amount,
				"purpose_type": purpose_type,
				"tenure": tenure,
				"iou_declaration": 1,
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def act(self, user, doc, action, **kwargs):
		frappe.set_user(user)
		try:
			if action == actions.APPROVE:
				actions.approve(doc.doctype, doc.name)
			elif action == actions.REJECT:
				actions.reject(doc.doctype, doc.name, kwargs.get("reason"))
			elif action == actions.MODIFY:
				actions.modify(doc.doctype, doc.name, **kwargs)
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc(doc.doctype, doc.name)

	def paid_iou(self, amount=100000, purpose_type="Other", tenure=None):
		doc = self.apply(amount, purpose_type, tenure)
		doc = self.act(self.hod_user, doc, actions.APPROVE)
		doc = self.act(self.finance_1, doc, actions.APPROVE)
		frappe.set_user(self.finance_2)
		try:
			advance.pay_advance(doc.name, self.bank)
		finally:
			frappe.set_user("Administrator")
		return frappe.get_doc("Employee Advance", doc.name)

	def make_claim(self, amounts, from_pocket=0):
		doc = frappe.get_doc(
			{
				"doctype": "Expense Claim",
				"employee": self.employee,
				"company": self.company,
				"posting_date": today(),
				"claim_from_pocket": from_pocket,
				"expenses": [
					{"expense_type": self.expense_type, "description": "Taxi", "amount": amount, "expense_date": today()}
					for amount in amounts
				],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc

	def emails_for(self, doc, recipient):
		queues = frappe.get_all(
			"Email Queue",
			filters={"reference_doctype": doc.doctype, "reference_name": doc.name},
			pluck="name",
		)
		return frappe.get_all("Email Queue Recipient", filters={"parent": ["in", queues or [""]], "recipient": recipient}, pluck="parent")

	# ------------------------------------------------------------ application

	def test_application_is_routed_to_the_line_manager_and_hod_is_notified(self):
		doc = self.apply()
		self.assertEqual(doc.workflow_state, routing.STATE_OPEN)
		self.assertEqual(doc.current_approver, self.hod_user)
		self.assertEqual(doc.proxy_approver, self.proxy)
		self.assertTrue(doc.repay_unclaimed_amount_from_salary)
		self.assertTrue(self.emails_for(doc, self.hod_user))

	def test_new_iou_is_blocked_while_another_is_pending(self):
		self.apply()
		with self.assertRaisesRegex(frappe.ValidationError, "pending approval"):
			self.apply()

	def test_new_iou_is_blocked_while_paid_iou_is_outstanding(self):
		self.paid_iou()
		with self.assertRaisesRegex(frappe.ValidationError, "not settled"):
			self.apply()

	def test_travel_iou_needs_a_tenure(self):
		with self.assertRaisesRegex(frappe.ValidationError, "tenure"):
			self.apply(purpose_type="Travel", tenure=None)

	def test_due_date_follows_the_sop_examples(self):
		# Tenure 15 days, paid 10/09/2023 → due 02/10/2023; Other paid 10/09/2023 → due 15/09/2023
		self.assertEqual(getdate(advance.due_date("Travel", "15", "2023-09-10")), getdate("2023-10-02"))
		self.assertEqual(getdate(advance.due_date("Other", None, "2023-09-10")), getdate("2023-09-15"))

	# ------------------------------------------------------------ approvals and payment

	def test_full_approval_and_payment(self):
		doc = self.paid_iou(purpose_type="Travel", tenure="10")
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.hod_approved_by, self.hod_user)
		self.assertEqual(doc.finance_1_approved_by, self.finance_1)
		self.assertEqual(doc.finance_2_approved_by, self.finance_2)
		self.assertEqual(flt(doc.paid_amount), 100000)
		self.assertEqual(getdate(doc.due_date), getdate(add_days(doc.payment_date, 17)))
		self.assertTrue(self.emails_for(doc, frappe.db.get_value("Employee", self.employee, "company_email")))

	def test_only_the_current_approver_can_approve(self):
		doc = self.apply()
		with self.assertRaises(frappe.PermissionError):
			self.act(self.finance_1, doc, actions.APPROVE)

	def test_proxy_can_approve_for_the_hod(self):
		doc = self.act(self.proxy, self.apply(), actions.APPROVE)
		self.assertEqual(doc.workflow_state, routing.STATE_HOD)
		self.assertEqual(doc.current_approver, self.finance_1)

	def test_finance_2_cannot_approve_without_paying(self):
		doc = self.act(self.hod_user, self.apply(), actions.APPROVE)
		doc = self.act(self.finance_1, doc, actions.APPROVE)
		self.assertEqual(actions.available_actions(doc, self.finance_2), [actions.PAY])
		with self.assertRaises(frappe.PermissionError):
			self.act(self.finance_2, doc, actions.APPROVE)

	def test_finance_1_approver_cannot_pay(self):
		doc = self.act(self.hod_user, self.apply(), actions.APPROVE)
		doc = self.act(self.finance_1, doc, actions.APPROVE)
		doc.db_set("current_approver", self.finance_1)
		frappe.set_user(self.finance_1)
		try:
			with self.assertRaises(frappe.PermissionError):
				advance.pay_advance(doc.name, self.bank)
		finally:
			frappe.set_user("Administrator")

	def test_reject_needs_a_reason_and_notifies_the_employee(self):
		doc = self.apply()
		with self.assertRaisesRegex(frappe.ValidationError, "reason"):
			self.act(self.hod_user, doc, actions.REJECT, reason=" ")
		doc = self.act(self.hod_user, doc, actions.REJECT, reason="Not budgeted")
		self.assertEqual(doc.workflow_state, routing.STATE_REJECTED)
		self.assertEqual(doc.rejected_stage, routing.HOD)
		self.assertEqual(doc.rejection_reason, "Not budgeted")
		self.assertIsNone(doc.current_approver)

	def test_rejected_iou_does_not_block_a_new_one(self):
		self.act(self.hod_user, self.apply(), actions.REJECT, reason="No")
		self.assertTrue(self.apply().name)

	def test_modify_changes_the_amount_and_keeps_a_comment(self):
		doc = self.act(self.hod_user, self.apply(), actions.MODIFY, advance_amount=80000)
		self.assertEqual(flt(doc.advance_amount), 80000)
		self.assertEqual(doc.workflow_state, routing.STATE_OPEN)
		self.assertTrue(frappe.db.exists("Comment", {"reference_name": doc.name, "comment_type": "Edit"}))

	# ------------------------------------------------------------ claims

	def approve_claim(self, doc):
		doc = self.act(self.hod_user, doc, actions.APPROVE)
		return self.act(self.finance_1, doc, actions.APPROVE)

	def test_claim_equal_to_iou_closes_it(self):
		iou = self.paid_iou()
		doc = self.approve_claim(self.make_claim([100000]))
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(flt(doc.total_advance_amount), 100000)
		self.assertEqual(flt(doc.grand_total), 0)
		self.assertEqual(advance.outstanding(frappe.get_doc("Employee Advance", iou.name)), 0)

	def test_claim_less_than_iou_reduces_outstanding(self):
		iou = self.paid_iou()
		self.approve_claim(self.make_claim([50000, 30000]))
		self.assertEqual(advance.outstanding(frappe.get_doc("Employee Advance", iou.name)), 20000)

	def test_claim_more_than_iou_pays_the_rest(self):
		iou = self.paid_iou()
		self.approve_claim(self.make_claim([80000]))
		doc = self.approve_claim(self.make_claim([30000]))
		self.assertEqual(flt(doc.total_advance_amount), 20000)
		self.assertEqual(flt(doc.grand_total), 10000)
		self.assertEqual(advance.outstanding(frappe.get_doc("Employee Advance", iou.name)), 0)
		self.assertEqual(actions.available_actions(doc, self.finance_1), [actions.PAY])

		frappe.set_user(self.finance_1)
		try:
			claim.pay_claim(doc.name, self.bank)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Expense Claim", doc.name, "status"), "Paid")

	def test_claim_without_open_iou_must_be_from_pocket(self):
		with self.assertRaisesRegex(frappe.ValidationError, "no open IOU"):
			self.make_claim([5000])
		doc = self.make_claim([5000], from_pocket=1)
		self.assertFalse(doc.advances)
		self.assertEqual(doc.current_approver, self.hod_user)

	def test_claim_after_due_date_is_blocked(self):
		iou = self.paid_iou()
		iou.db_set("due_date", add_days(today(), -1))
		with self.assertRaisesRegex(frappe.ValidationError, "was due"):
			self.make_claim([1000])

	def test_second_claim_waits_for_the_first(self):
		self.paid_iou()
		self.make_claim([1000])
		with self.assertRaisesRegex(frappe.ValidationError, "still pending approval"):
			self.make_claim([1000])

	def test_modify_claim_row(self):
		self.paid_iou()
		doc = self.make_claim([10000])
		doc = self.act(self.hod_user, doc, actions.MODIFY, expenses=[{"name": doc.expenses[0].name, "amount": 9000}])
		self.assertEqual(flt(doc.expenses[0].amount), 9000)
		self.assertEqual(flt(doc.advances[0].allocated_amount), 9000)

	# ------------------------------------------------------------ scheduled jobs

	def test_salary_recovery_skips_claims_in_approval(self):
		iou = self.paid_iou()
		iou.db_set("due_date", add_days(today(), -1))

		with patch.object(frappe.db, "commit"), patch("centhr.iou.scheduler.recover", return_value="AS-1") as recover:
			scheduler.schedule_salary_recovery(force=True)
			self.assertIn(iou.name, [call.args[0].name for call in recover.call_args_list])

			# A claim filed before the due date (still in approval) holds the deduction back
			recover.reset_mock()
			iou.db_set("due_date", today())
			self.make_claim([1000])
			iou.db_set("due_date", add_days(today(), -1))
			scheduler.schedule_salary_recovery(force=True)
			self.assertNotIn(iou.name, [call.args[0].name for call in recover.call_args_list])

	def test_next_payroll_date(self):
		with patch("centhr.iou.settings.get_int", return_value=0):
			self.assertEqual(scheduler.next_payroll_date("2026-02-10"), getdate("2026-02-28"))
		with patch("centhr.iou.settings.get_int", return_value=25):
			self.assertEqual(scheduler.next_payroll_date("2026-02-10"), getdate("2026-02-25"))
			self.assertEqual(scheduler.next_payroll_date("2026-02-26"), getdate("2026-03-25"))

	def test_escalation_notifies_the_proxy_once(self):
		doc = self.apply()
		doc.db_set("pending_since", add_to_date(now_datetime(), hours=-25))
		with patch.object(frappe.db, "commit"):
			scheduler.escalate_to_proxies()
			scheduler.escalate_to_proxies()
		self.assertTrue(frappe.db.get_value("Employee Advance", doc.name, "escalated_at"))
		self.assertEqual(len(self.emails_for(doc, self.proxy)), 1)

	# ------------------------------------------------------------ dashboard and reports

	def test_dashboard_lists_claims_with_actions_for_the_approver(self):
		from centhr.api.iou import get_iou_dashboard_data

		self.paid_iou()
		claim_doc = self.make_claim([30000])
		frappe.set_user(self.hod_user)
		try:
			data = get_iou_dashboard_data(focus="mine")
		finally:
			frappe.set_user("Administrator")
		row = next(r for r in data["records"] if r["name"] == claim_doc.name)
		self.assertEqual(row["actions"], [actions.APPROVE, actions.REJECT, actions.MODIFY])
		self.assertEqual(row["amount_from_iou"], 30000)
		self.assertEqual(row["approvers"]["hod"]["status"], "Pending")
		self.assertEqual(data["stats"]["waiting_for_me"]["count"], len(data["records"]))

	def test_reports_show_the_outstanding_balance(self):
		from centhr.centhr.report.iou_advance_report.iou_advance_report import execute as advance_report
		from centhr.centhr.report.iou_advance_summary.iou_advance_summary import execute as summary_report

		iou = self.paid_iou()
		self.approve_claim(self.make_claim([40000]))
		iou.db_set("due_date", add_days(today(), -10))

		_columns, rows = advance_report({"company": self.company, "employee": self.employee})
		self.assertEqual([(r.name, r.balance) for r in rows], [(iou.name, 60000)])

		_columns, rows = summary_report({"company": self.company, "employee": self.employee})
		self.assertEqual(rows[0].days_overdue, 10)
		self.assertEqual(rows[0].overdue_0_30, 60000)
