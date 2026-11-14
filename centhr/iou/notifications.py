"""The emails of the IOU SOP. The texts follow the SOP wording.

Rules (SOP, Pre-Information):
- Every step tells the employee, and asks the next approver to act.
- A rejection or modification by the HOD goes to the employee only. One by Finance (or a proxy of
  Finance) goes to the employee with the HOD in copy.
"""

import frappe
from frappe.utils import fmt_money, formatdate, get_url

from centhr.iou import ADVANCE, routing, settings

DASHBOARD_ROUTE = "/centhr/iou/dashboard"


# ---------------------------------------------------------------- state changes


def on_state_change(doc):
	"""on_update / on_submit of an IOU document: send the emails of the step that just happened."""
	if frappe.flags.centhr_migration or frappe.flags.in_import or frappe.flags.in_install:
		return

	previous = doc.get_doc_before_save()
	state = routing.state_of(doc)
	if previous and routing.state_of(previous) == state:
		return

	ctx = Context(doc)
	if not previous:
		ctx.notify_submitted()
	elif state == routing.STATE_REJECTED:
		ctx.notify_rejected(doc.flags.iou_acted_as or doc.get("rejected_stage") or "")
	elif state == routing.STATE_HOD:
		ctx.notify_approved(routing.HOD)
	elif state == routing.STATE_FINANCE_1:
		ctx.notify_approved(routing.FINANCE_1)
	elif state == routing.STATE_APPROVED and doc.doctype != ADVANCE:
		# Paid IOUs are announced by pay_advance, once the payment and due date exist
		ctx.notify_approved(routing.FINANCE_1)


def notify_modified(doc, acted_as: str):
	Context(doc).notify_modified(acted_as)


def notify_paid(doc):
	ctx = Context(doc)
	ctx.send(
		[ctx.employee_email],
		f"IOU {doc.name} paid",
		f"Finance 2 – {ctx.name_of(doc.get('finance_2_approved_by'))} has approved your IOU – {doc.name} of amount "
		f"{ctx.amount}. Please ensure that you settle this IOU before the due date - {formatdate(doc.due_date, 'dd/MM/yyyy')}. "
		"Failure to do so will result in the outstanding amount being deducted from your payroll.",
	)


def notify_proxy(doc):
	"""The approver has not acted in time: ask their proxy, in the SOP's 'in the absence of' wording."""
	ctx = Context(doc)
	stage = routing.stage_of(doc)
	absent = f"{stage} - {ctx.name_of(doc.current_approver)}"
	if stage == routing.HOD:
		message = ctx.submitted_text()
	else:
		previous_stage = routing.HOD if stage == routing.FINANCE_1 else routing.FINANCE_1
		message = ctx.approved_text_for_next(previous_stage)
	ctx.send(
		[doc.proxy_approver],
		f"{ctx.label} {doc.name} waiting for your approval",
		f"{message.rstrip('.')} in the absence of {absent}.",
		link=True,
	)


def notify_due_reminder(doc, outstanding: float):
	ctx = Context(doc)
	ctx.send(
		[ctx.employee_email],
		f"IOU {doc.name} is due on {formatdate(doc.due_date, 'dd/MM/yyyy')}",
		f"IOU – {doc.name} of outstanding amount {ctx.money(outstanding)} is due on "
		f"{formatdate(doc.due_date, 'dd/MM/yyyy')}. Please submit your expense claim before the due date. "
		"Any amount outstanding after the due date will be deducted from your payroll.",
	)


def notify_salary_adjustment(doc, outstanding: float, payroll_date):
	ctx = Context(doc)
	cc = [ctx.hod_email, settings.finance_1(), settings.finance_2(), *hr_users()]
	ctx.send(
		[ctx.employee_email],
		f"IOU {doc.name} will be adjusted with your salary",
		f"IOU – {doc.name} of outstanding amount {ctx.money(outstanding)} is open & will be adjusted with your "
		f"salary in the {formatdate(payroll_date, 'MMM yyyy')} payroll cycle.",
		cc=cc,
	)


def hr_users() -> list[str]:
	return [
		user
		for user in frappe.get_all(
			"Has Role", filters={"role": "HR Manager", "parenttype": "User"}, pluck="parent", distinct=True
		)
		if user not in ("Administrator", "Guest") and frappe.db.get_value("User", user, "enabled")
	]


# ---------------------------------------------------------------- texts


class Context:
	def __init__(self, doc):
		self.doc = doc
		self.is_advance = doc.doctype == ADVANCE
		self.advance = None if self.is_advance else claim_advance(doc)
		self.label = "IOU" if self.is_advance else ("IOU Claim" if self.advance else "Expense Claim")
		self.employee_email = employee_email(doc.employee)
		self.hod_email = doc.get("line_manager")
		self.amount = self.money(doc_amount(doc))

	def money(self, value) -> str:
		return f"{self.doc.currency or ''} {fmt_money(value or 0, precision=2)}".strip()

	def name_of(self, user) -> str:
		return settings.full_name(user)

	@property
	def application(self) -> str:
		return "IOU Application" if self.is_advance else f"{self.label} Application"

	def submitted_text(self) -> str:
		emp = self.doc.employee_name or self.doc.employee
		if self.is_advance:
			return (
				f"{emp} has submitted an IOU application request of {self.amount} for your review & approval. "
				"Kindly review & approve through this link."
			)
		if self.advance:
			return (
				f"{emp} has submitted an IOU claim - {self.doc.name} request of amount {self.amount} against "
				f"IOU – {self.advance} for your review & approval. Kindly review & approve through this link."
			)
		return (
			f"{emp} has submitted an Expense claim - {self.doc.name} request of amount {self.amount} for your "
			"review & approval. Kindly review & approve through this link."
		)

	def approved_text_for_next(self, stage: str) -> str:
		"""To the next approver: '<stage> – <name> has approved IOU – …'."""
		doc = self.doc
		by = self.name_of(doc.get(routing.APPROVED_BY_FIELD[stage]))
		pay = " the payment" if self.is_advance and stage == routing.FINANCE_1 else ""
		return (
			f"{stage} – {by} has approved {self.label} – {doc.name} of amount {self.amount} of Employee – "
			f"{doc.employee_name or doc.employee}. Kindly review and approve{pay} through this link."
		)

	def notify_submitted(self):
		if self.doc.current_approver:
			self.send([self.doc.current_approver], f"{self.label} {self.doc.name} waiting for your approval", self.submitted_text(), link=True)

	def notify_approved(self, stage: str):
		doc = self.doc
		by = self.name_of(doc.get(routing.APPROVED_BY_FIELD[stage]))
		what = "IOU" if self.is_advance else self.application
		text = f"{stage} – {by} has approved your {what} – {doc.name} of amount {self.amount}"

		next_stage = routing.stage_of(doc) if doc.current_approver else None
		next_name = self.name_of(doc.current_approver)
		if next_stage == routing.FINANCE_2:
			text += f". It is now pending with Finance 2 - {next_name} for payment approval"
		elif next_stage:
			text += f". It is now pending for {next_stage} - {next_name} Approval"

		self.send([self.employee_email], f"{self.label} {doc.name} approved by {stage}", f"{text}.")
		if next_stage:
			self.send(
				[doc.current_approver],
				f"{self.label} {doc.name} waiting for your approval",
				self.approved_text_for_next(stage),
				link=True,
			)

	def notify_rejected(self, acted_as: str):
		doc = self.doc
		self.send(
			[self.employee_email],
			f"{self.label} {doc.name} rejected",
			f"Your {self.application} - {doc.name} has been rejected by {acted_as} – "
			f"{self.name_of(doc.get('rejected_by'))} for the below reason.<br><br>Reason: {frappe.utils.escape_html(doc.get('rejection_reason') or '')}",
			cc=self.cc_for(acted_as),
		)

	def notify_modified(self, acted_as: str):
		doc = self.doc
		self.send(
			[self.employee_email],
			f"{self.label} {doc.name} modified",
			f"Your {self.application} - {doc.name} has been modified by {acted_as} – {self.name_of(frappe.session.user)}.",
			cc=self.cc_for(acted_as),
		)

	def cc_for(self, acted_as: str) -> list[str]:
		# Only an HOD action stays between the HOD and the employee
		return [] if acted_as == routing.HOD else [self.hod_email]

	def send(self, recipients: list, subject: str, message: str, cc: list | None = None, link: bool = False):
		recipients = [r for r in recipients if r]
		if not recipients:
			return
		if link:
			url = get_url(DASHBOARD_ROUTE)
			message = f'{message}<br><br><a href="{url}">{url}</a>'
		try:
			frappe.sendmail(
				recipients=recipients,
				cc=[c for c in (cc or []) if c and c not in recipients],
				subject=subject,
				message=message,
				reference_doctype=self.doc.doctype,
				reference_name=self.doc.name,
			)
		except Exception:
			# A missing or broken email account must not undo the approval step itself
			frappe.log_error(title=f"IOU email not sent: {subject}", reference_doctype=self.doc.doctype, reference_name=self.doc.name)


def claim_advance(doc) -> str | None:
	return next((row.employee_advance for row in doc.get("advances") or [] if row.allocated_amount), None)


def doc_amount(doc) -> float:
	if doc.doctype == ADVANCE:
		return doc.advance_amount
	return doc.total_claimed_amount or sum(row.amount or 0 for row in doc.get("expenses") or [])


def employee_email(employee: str) -> str | None:
	values = frappe.db.get_value(
		"Employee", employee, ["prefered_email", "company_email", "personal_email", "user_id"], as_dict=True
	)
	if not values:
		return None
	return values.prefered_email or values.company_email or values.user_id or values.personal_email
