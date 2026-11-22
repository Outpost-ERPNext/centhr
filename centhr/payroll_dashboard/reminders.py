"""Reminders about what payroll waits for: unmarked attendance goes to the employee, an open leave
application or attendance request to whoever approves it."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import formatdate

from centhr.payroll_dashboard.attendance import AttendanceSummary
from centhr.payroll_dashboard.scope import Scope

LOG = "Payroll Reminder"
UNMARKED, LEAVE, REQUEST = "Unmarked Attendance", "Leave Application", "Attendance Request"


class Reminders:
	def __init__(self, scope: Scope):
		self.scope = scope
		self.period = (formatdate(scope.from_date), formatdate(scope.to_date))

	def send(self, employees: list[str] | None = None) -> dict:
		"""Send to the given employees, or to everyone in the cycle with something open. One email per
		employee about their own attendance, and one per approver about everything they have to decide."""
		frappe.has_permission("Attendance", "read", throw=True)
		rows = [
			frappe._dict(r) for r in self.scope.get_employees() if not employees or r["name"] in employees
		]
		reminded = self.remind_employees(rows) + self.remind_approvers(rows)
		return {"sent": len(reminded), "recipients": sorted(set(reminded))}

	def remind_employees(self, rows: list) -> list[str]:
		summary = AttendanceSummary(self.scope).summarize(rows)
		emails = get_emails([row.name for row in rows])
		sent = []
		for row in rows:
			unmarked = int(summary[row.name]["unmarked"])
			email = emails.get(row.name)
			if not unmarked or not email:
				continue
			self.mail(
				email,
				row.employee_name,
				_("Mark your attendance for {0} to {1}").format(*self.period),
				_("Your attendance is not marked on some working days of this pay cycle."),
				[_("{0} working day(s) without attendance").format(unmarked)],
			)
			self.log(row, UNMARKED, email)
			sent.append(email)
		return sent

	def remind_approvers(self, rows: list) -> list[str]:
		by_name = {row.name: row for row in rows}
		pending = defaultdict(list)
		for kind, document in self.get_open_documents(list(by_name)):
			approver = get_approver(document, by_name[document.employee])
			if approver:
				pending[approver].append((kind, document))

		for approver, documents in pending.items():
			self.mail(
				approver,
				frappe.db.get_value("User", approver, "full_name") or approver,
				_("Approvals waiting for payroll, {0} to {1}").format(*self.period),
				_("These requests of your team are still open. Please approve or reject them."),
				[self.describe(kind, document) for kind, document in documents],
			)
			for kind, document in documents:
				self.log(by_name[document.employee], kind, approver)
		return list(pending)

	def get_open_documents(self, employees: list[str]) -> list[tuple]:
		documents = []
		for kind, extra, fields in ((LEAVE, {"status": "Open"}, ["leave_approver"]), (REQUEST, {}, [])):
			rows = frappe.get_all(
				kind,
				filters={
					"employee": ["in", employees or [""]],
					"docstatus": 0,
					"from_date": ["<=", self.scope.to_date],
					"to_date": [">=", self.scope.from_date],
					**extra,
				},
				fields=["name", "employee", "employee_name", "from_date", "to_date", *fields],
			)
			documents += [(kind, row) for row in rows]
		return documents

	def describe(self, kind: str, document) -> str:
		return _("{0}: {1} {2}, {3} to {4}").format(
			document.employee_name,
			_(kind),
			document.name,
			formatdate(document.from_date),
			formatdate(document.to_date),
		)

	def mail(self, recipient: str, name: str, subject: str, intro: str, items: list[str]) -> None:
		frappe.sendmail(
			recipients=[recipient],
			subject=subject,
			template="payroll_reminder",
			args={
				"recipient_name": name,
				"intro": intro,
				"items": items,
				"from_date": self.period[0],
				"to_date": self.period[1],
			},
		)

	def log(self, employee, kind: str, recipient: str) -> None:
		frappe.get_doc(
			{
				"doctype": LOG,
				"employee": employee.name,
				"company": employee.company,
				"kind": kind,
				"recipient": recipient,
				"from_date": self.scope.from_date,
				"to_date": self.scope.to_date,
			}
		).insert(ignore_permissions=True)


def get_last_sent(employees: list[str], scope: Scope) -> dict:
	"""When each employee's last reminder of the cycle went out."""
	if not employees:
		return {}
	rows = frappe.get_all(
		LOG,
		filters={"employee": ["in", employees], "from_date": scope.from_date, "to_date": scope.to_date},
		fields=["employee", {"MAX": "creation", "as": "sent_on"}],
		group_by="employee",
	)
	return {row.employee: row.sent_on for row in rows}


def get_approver(document, employee) -> str | None:
	"""The document's own approver, else the employee's line manager, else the department's approver."""
	if document.get("leave_approver"):
		return document.leave_approver
	manager = frappe.db.get_value("Employee", employee.name, "reports_to")
	user = manager and frappe.db.get_value("Employee", manager, "user_id")
	if user:
		return user
	if not employee.department:
		return None
	return frappe.db.get_value(
		"Department Approver",
		{"parent": employee.department, "parentfield": "leave_approvers"},
		"approver",
		order_by="idx asc",
	)


def get_emails(employees: list[str]) -> dict[str, str]:
	rows = frappe.get_all(
		"Employee",
		filters={"name": ["in", employees or [""]]},
		fields=["name", "user_id", "company_email", "personal_email"],
	)
	return {row.name: row.user_id or row.company_email or row.personal_email for row in rows}
