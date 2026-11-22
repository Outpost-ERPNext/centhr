"""The payroll run of one company and period, step by step as the Payroll Entry form does it in Desk:
submit the entry (HRMS creates the draft salary slips), submit the slips, then make the bank entry."""

import frappe
from frappe import _
from frappe.utils import getdate

from centhr.payroll_dashboard import confidential, payment_request

# Bank and Cash journal entries pay the payroll out; HRMS links them to the entry by reference
PAYOUT_VOUCHER_TYPES = ["Bank Entry", "Cash Entry"]


BATCHES = confidential.STANDARD_BATCHES


class PayrollGenerator:
	"""Creates and submits a monthly Payroll Entry of a period: the Regular batch for employees still
	with the company, the Exited batch for those whose relieving date is in the period, or one of the
	company's confidential batches for the employees on its salary structures."""

	def __init__(self, company: str, start_date: str, end_date: str, batch: str = "Regular"):
		confidential.check_may_use(company, batch)
		self.company = company
		self.start_date = getdate(start_date)
		self.end_date = getdate(end_date)
		self.batch = batch

	def run(self) -> str:
		self.check_no_entry_exists()
		# Insert first, as Desk does: the employee query reads defaults that insert sets
		entry = self.make_entry().insert()
		entry.fill_employee_details()
		self.keep_batch_employees(entry)
		entry.submit()
		return entry.name

	def make_entry(self):
		defaults = frappe.get_cached_value(
			"Company",
			self.company,
			["default_currency", "default_payroll_payable_account", "cost_center", "default_bank_account"],
			as_dict=True,
		)
		if not defaults.default_payroll_payable_account:
			frappe.throw(_("Set the Default Payroll Payable Account of company {0} first.").format(self.company))

		return frappe.get_doc(
			{
				"doctype": "Payroll Entry",
				"company": self.company,
				"centhr_batch": self.batch,
				# The accrual is booked at the end of the period it pays for
				"posting_date": self.end_date,
				"payroll_frequency": "Monthly",
				"start_date": self.start_date,
				"end_date": self.end_date,
				"currency": defaults.default_currency,
				"exchange_rate": 1,
				"payroll_payable_account": defaults.default_payroll_payable_account,
				"cost_center": defaults.cost_center,
				"payment_account": defaults.default_bank_account,
			}
		)

	def keep_batch_employees(self, entry) -> None:
		"""HRMS lists everyone who is due a salary in the period. Each batch keeps its own part."""
		batch_of = self.get_employee_batches([row.employee for row in entry.employees])
		keep = [row for row in entry.employees if batch_of[row.employee] == self.batch]
		if not keep:
			frappe.throw(
				_("No employee of {0} is waiting for a salary slip in the {1} batch of this pay cycle.").format(
					self.company, _(self.batch)
				),
				title=_("Nobody to Pay"),
			)
		entry.set("employees", keep)
		entry.number_of_employees = len(keep)

	def get_employee_batches(self, employees: list[str]) -> dict[str, str]:
		"""A confidential salary structure has its own batch, also for those who left. Of everyone
		else, those who left in the period are the Exited batch."""
		confidential_batch = confidential.get_batch_of(self.company)
		structure_of = self.get_structures(employees) if confidential_batch else {}
		exited = self.get_exited(employees)
		return {
			employee: confidential_batch.get(structure_of.get(employee))
			or ("Exited" if employee in exited else "Regular")
			for employee in employees
		}

	def get_structures(self, employees: list[str]) -> dict[str, str]:
		"""Each employee's salary structure as assigned by the end of the period."""
		rows = frappe.get_all(
			"Salary Structure Assignment",
			filters={"employee": ["in", employees or [""]], "docstatus": 1, "from_date": ["<=", self.end_date]},
			fields=["employee", "salary_structure"],
			order_by="from_date asc",
		)
		return {row.employee: row.salary_structure for row in rows}

	def get_exited(self, employees: list[str]) -> set[str]:
		if not employees:
			return set()
		return set(
			frappe.get_all(
				"Employee",
				filters={
					"name": ["in", employees],
					"relieving_date": ["between", [self.start_date, self.end_date]],
				},
				pluck="name",
			)
		)

	def check_no_entry_exists(self):
		existing = frappe.db.exists(
			"Payroll Entry",
			{
				"company": self.company,
				"centhr_batch": self.batch,
				"start_date": self.start_date,
				"end_date": self.end_date,
				"docstatus": ["!=", 2],
			},
		)
		if existing:
			frappe.throw(
				_("{0} payroll entry {1} already exists for this period.").format(_(self.batch), existing)
			)


class PayrollRun:
	"""One Payroll Entry and the step it waits for. HRMS checks permissions in each step it runs."""

	def __init__(self, payroll_entry: str):
		self.entry = frappe.get_doc("Payroll Entry", payroll_entry)
		self.entry.check_permission("read")

	def summary(self) -> dict:
		entry = self.entry
		payouts = self.get_payouts()
		return {
			"name": entry.name,
			"company": entry.company,
			"batch": entry.get("centhr_batch") or "Regular",
			"status": entry.status,
			"docstatus": entry.docstatus,
			"number_of_employees": entry.number_of_employees,
			"salary_slips_created": entry.salary_slips_created,
			"salary_slips_submitted": entry.salary_slips_submitted,
			"payment_account": entry.payment_account,
			"error_message": entry.error_message,
			"payouts": payouts,
			"payment_request": payment_request.get_latest("Payroll", entry.name),
			"has_withheld_salaries": any(e.is_salary_withheld for e in entry.employees),
			"next_step": self.next_step(payouts),
		}

	def next_step(self, payouts: list) -> str | None:
		entry = self.entry
		if entry.docstatus == 2 or entry.status == "Queued":
			return None
		if entry.docstatus == 0:
			return "submit"
		if not entry.salary_slips_created:
			return "create_slips"
		if not entry.salary_slips_submitted:
			return "submit_slips"
		if payouts:
			return None
		# Accounts approves the payment request before the bank entry is made
		request = payment_request.get_latest("Payroll", entry.name)
		if not payment_request.is_open(request):
			return "payment_request"
		return "bank_entry" if request["status"] == payment_request.APPROVED else None

	def run_step(self, step: str, payment_account: str | None = None):
		steps = {
			"submit": self.submit,
			"create_slips": self.entry.create_salary_slips,
			"submit_slips": self.entry.submit_salary_slips,
			"payment_request": lambda: self.request_payment(payment_account),
			"bank_entry": lambda: self.pay_out(payment_account),
			"release_withheld": lambda: self.pay_out(payment_account, withheld=True),
			"cancel": self.cancel,
		}
		if step not in steps:
			frappe.throw(_("Unknown payroll step {0}.").format(step))
		steps[step]()

	def submit(self):
		if not self.entry.employees:
			self.entry.fill_employee_details()
			self.entry.save()
		self.entry.submit()

	def request_payment(self, payment_account: str | None):
		if not self.entry.salary_slips_submitted:
			frappe.throw(_("Submit the salary slips before requesting their payment."))
		self.set_payment_account(payment_account)
		payment_request.request_for_run(self.entry)

	def pay_out(self, payment_account: str | None, withheld: bool = False):
		"""Creates the draft bank entry, as Desk does; it is reviewed and submitted in Accounts.
		Salaries are paid once their payment request is approved; withheld ones when they are released."""
		if not withheld:
			self.check_request_approved()
		self.set_payment_account(payment_account)
		bank_entry = self.entry.make_bank_entry(for_withheld_salaries=withheld)
		if bank_entry and not withheld:
			payment_request.link_bank_entry(self.entry.name, bank_entry.get("name"))

	def check_request_approved(self):
		request = payment_request.get_latest("Payroll", self.entry.name)
		if not request or request["status"] != payment_request.APPROVED:
			frappe.throw(
				_("The payment request of {0} must be approved before its bank entry is made.").format(
					self.entry.name
				),
				title=_("Payment Not Approved"),
			)

	def cancel(self):
		self.entry.cancel()
		payment_request.close_for_cancelled_run(self.entry.name)

	def set_payment_account(self, account: str | None):
		"""Payment Account can change on a submitted entry; HRMS pays out of it."""
		account = account or self.entry.payment_account
		if not account:
			frappe.throw(_("Choose the bank or cash account to pay the salaries from."))
		valid = frappe.db.exists(
			"Account",
			{"name": account, "company": self.entry.company, "is_group": 0, "account_type": ["in", ["Bank", "Cash"]]},
		)
		if not valid:
			frappe.throw(_("{0} is not a bank or cash account of company {1}.").format(account, self.entry.company))
		if account != self.entry.payment_account:
			self.entry.check_permission("write")
			self.entry.db_set("payment_account", account)

	def get_payouts(self) -> list[dict]:
		return frappe.get_all(
			"Journal Entry",
			filters=[
				["Journal Entry Account", "reference_type", "=", "Payroll Entry"],
				["Journal Entry Account", "reference_name", "=", self.entry.name],
				["voucher_type", "in", PAYOUT_VOUCHER_TYPES],
				["docstatus", "!=", 2],
			],
			fields=["name", "docstatus"],
			distinct=True,
		)
