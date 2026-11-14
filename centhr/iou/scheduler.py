"""Scheduled IOU jobs: due date reminders, salary recovery of overdue IOUs, and proxy escalation."""

import frappe
from frappe.utils import add_days, add_months, add_to_date, get_last_day, getdate, now_datetime, today

from centhr.iou import ADVANCE, IOU_DOCTYPES, notifications, settings
from centhr.iou.advance import outstanding
from centhr.iou.claim import claims_in_approval


def paid_advances(**filters) -> list:
	"""Paid IOUs with an outstanding amount, as frappe._dicts with `outstanding_amount`."""
	rows = frappe.get_all(
		ADVANCE,
		filters={"docstatus": 1, "paid_amount": [">", 0], **filters},
		fields=["name", "employee", "company", "currency", "due_date", "paid_amount", "claimed_amount", "return_amount"],
	)
	for row in rows:
		row.outstanding_amount = outstanding(row)
	return [row for row in rows if row.outstanding_amount > 0]


# ---------------------------------------------------------------- daily


def send_due_reminders():
	"""SOP: 3 days before the due date, remind the employee to submit the expense claim."""
	reminder_date = add_days(today(), settings.get_int("iou_due_reminder_days"))
	for row in paid_advances(due_date=reminder_date):
		notifications.notify_due_reminder(frappe.get_doc(ADVANCE, row.name), row.outstanding_amount)


def next_payroll_date(date=None):
	"""The next payroll run on or after the date. Payroll Day 0 means the last day of the month."""
	date = getdate(date or today())
	day = settings.get_int("iou_payroll_day")

	def in_month(month_date):
		last = get_last_day(month_date)
		return last if not day or day >= last.day else month_date.replace(day=day)

	payroll = in_month(date)
	return payroll if payroll >= date else in_month(add_months(date.replace(day=1), 1))


def schedule_salary_recovery(force: bool = False):
	"""SOP: 7 days before payroll, overdue IOUs are scheduled for deduction from salary and the employee is told
	(HOD, HR and Finance in copy). IOUs with a claim still in approval are skipped."""
	payroll_date = next_payroll_date()
	notice_date = add_days(payroll_date, -settings.get_int("iou_payroll_notice_days"))
	if not force and getdate(today()) != getdate(notice_date):
		return []

	overdue = paid_advances(due_date=["<", today()])
	in_approval = claims_in_approval([row.name for row in overdue])
	scheduled = set(
		frappe.get_all(
			"Additional Salary",
			filters={"ref_doctype": ADVANCE, "ref_docname": ["in", [row.name for row in overdue] or [""]], "docstatus": ["<", 2]},
			pluck="ref_docname",
		)
	)

	created = []
	for row in overdue:
		if row.name in in_approval or row.name in scheduled:
			continue
		try:
			created.append(recover(row, payroll_date))
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"IOU salary recovery failed for {row.name}")
		else:
			frappe.db.commit()
	return created


def recover(row, payroll_date) -> str:
	from centhr.payroll_dashboard.advances import create_salary_recovery

	doc = frappe.get_doc(ADVANCE, row.name)
	additional_salary = create_salary_recovery(
		doc, settings.salary_component(), payroll_date, row.outstanding_amount, ignore_permissions=True
	)
	notifications.notify_salary_adjustment(doc, row.outstanding_amount, payroll_date)
	return additional_salary


# ---------------------------------------------------------------- hourly


def escalate_to_proxies():
	"""SOP: when the approver has not acted within 24 hours, ask their proxy. Once per step."""
	cutoff = add_to_date(now_datetime(), hours=-settings.get_int("iou_escalation_hours"))
	for doctype in IOU_DOCTYPES:
		for name in frappe.get_all(
			doctype,
			filters={
				"docstatus": 0,
				"pending_since": ["<=", cutoff],
				"escalated_at": ["is", "not set"],
				"proxy_approver": ["is", "set"],
			},
			pluck="name",
		):
			doc = frappe.get_doc(doctype, name)
			notifications.notify_proxy(doc)
			doc.db_set("escalated_at", now_datetime(), update_modified=False)
		frappe.db.commit()
