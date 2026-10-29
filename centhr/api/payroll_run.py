"""The payroll run of one company and period, step by step as the Payroll Entry form does it in Desk:
submit the entry (HRMS creates the draft salary slips), submit the slips, then make the bank entry."""

import frappe
from frappe import _
from frappe.utils import getdate

# Bank and Cash journal entries pay the payroll out; HRMS links them to the entry by reference
PAYOUT_VOUCHER_TYPES = ["Bank Entry", "Cash Entry"]


class PayrollGenerator:
	"""Creates and submits the monthly Payroll Entry of a period."""

	def __init__(self, company: str, start_date: str, end_date: str):
		self.company = company
		self.start_date = getdate(start_date)
		self.end_date = getdate(end_date)

	def run(self) -> str:
		self.check_no_entry_exists()
		# Insert first, as Desk does: the employee query reads defaults that insert sets
		entry = self.make_entry().insert()
		entry.fill_employee_details()
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

	def check_no_entry_exists(self):
		existing = frappe.db.exists(
			"Payroll Entry",
			{
				"company": self.company,
				"start_date": self.start_date,
				"end_date": self.end_date,
				"docstatus": ["!=", 2],
			},
		)
		if existing:
			frappe.throw(_("Payroll Entry {0} already exists for this period.").format(existing))


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
			"status": entry.status,
			"docstatus": entry.docstatus,
			"number_of_employees": entry.number_of_employees,
			"salary_slips_created": entry.salary_slips_created,
			"salary_slips_submitted": entry.salary_slips_submitted,
			"payment_account": entry.payment_account,
			"error_message": entry.error_message,
			"payouts": payouts,
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
		if not payouts:
			return "bank_entry"
		return None

	def run_step(self, step: str, payment_account: str | None = None):
		steps = {
			"submit": self.submit,
			"create_slips": self.entry.create_salary_slips,
			"submit_slips": self.entry.submit_salary_slips,
			"bank_entry": lambda: self.pay_out(payment_account),
			"release_withheld": lambda: self.pay_out(payment_account, withheld=True),
			"cancel": self.entry.cancel,
		}
		if step not in steps:
			frappe.throw(_("Unknown payroll step {0}.").format(step))
		steps[step]()

	def submit(self):
		if not self.entry.employees:
			self.entry.fill_employee_details()
			self.entry.save()
		self.entry.submit()

	def pay_out(self, payment_account: str | None, withheld: bool = False):
		"""Creates the draft bank entry, as Desk does; it is reviewed and submitted in Accounts."""
		self.set_payment_account(payment_account)
		self.entry.make_bank_entry(for_withheld_salaries=withheld)

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
