# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Email OTP for the Attendance (Employee Checkin) and Leave Application web forms.

The web forms are open to guests, so the code proves that the person who submits the form
can read the employee's company email. The web form JS calls `send_otp` and `verify_otp`,
then sends the token from `verify_otp` with the form data. `validate_web_form_otp` checks
the token before the record is inserted, so the check cannot be skipped from the browser.
"""

import hashlib
import hmac
import json
import secrets
import time

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

OTP_DIGITS = 6
OTP_TTL = 10 * 60
TOKEN_TTL = 10 * 60
MAX_ATTEMPTS = 5


@frappe.whitelist(allow_guest=True, methods=["POST"])
# Per employee, not per IP, so nobody can flood an employee's inbox from many addresses
@rate_limit(key="employee", limit=5, seconds=OTP_TTL, ip_based=False)
def send_otp(employee: str) -> str:
	email = get_company_email(employee)
	otp = f"{secrets.randbelow(10**OTP_DIGITS):0{OTP_DIGITS}d}"
	set_otp(employee, {"hash": hash_otp(employee, otp), "attempts": 0, "expires_at": time.time() + OTP_TTL})

	frappe.sendmail(
		recipients=[email],
		subject=_("Your verification code"),
		message=_(
			"Your verification code is <b>{0}</b>. It expires in {1} minutes.<br><br>"
			"If you did not request this code, ignore this email."
		).format(otp, OTP_TTL // 60),
		now=True,
	)
	return mask_email(email)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=30, seconds=OTP_TTL)
def verify_otp(employee: str, otp: str) -> str:
	stored = frappe.cache.get_value(otp_key(employee))
	if not stored or stored["expires_at"] < time.time():
		frappe.throw(_("The code has expired. Request a new code."), title=_("Code Expired"))

	if not hmac.compare_digest(stored["hash"], hash_otp(employee, (otp or "").strip())):
		stored["attempts"] += 1
		if stored["attempts"] >= MAX_ATTEMPTS:
			frappe.cache.delete_value(otp_key(employee))
			frappe.throw(_("Too many wrong codes. Request a new code."), title=_("Wrong Code"))
		set_otp(employee, stored)
		frappe.throw(_("The code is not correct."), title=_("Wrong Code"))

	frappe.cache.delete_value(otp_key(employee))
	token = secrets.token_urlsafe(32)
	frappe.cache.set_value(token_key(token), employee, expires_in_sec=TOKEN_TTL)
	return token


def validate_web_form_otp(doc, method=None):
	"""before_insert: a web form submission needs a verified token for the same employee."""
	if not frappe.flags.in_web_form:
		return

	token = get_submitted_token()
	key = token_key(token) if token else None
	if not key or frappe.cache.get_value(key) != doc.employee:
		frappe.throw(
			_("Verify the code sent to the employee's company email before you submit."),
			title=_("Verification Required"),
		)

	# One token per submission. Keep it if the insert fails, so the user can correct the form.
	frappe.db.after_commit.add(lambda: frappe.cache.delete_value(key))


def get_company_email(employee: str) -> str:
	email = frappe.db.get_value("Employee", {"name": employee, "status": "Active"}, "company_email")
	if not email:
		frappe.throw(_("No company email is set for this employee. Contact HR."), title=_("Cannot Send Code"))
	return email


def get_submitted_token() -> str | None:
	data = frappe.form_dict.get("data")
	if isinstance(data, str):
		data = json.loads(data)
	return (data or {}).get("otp_token")


def set_otp(employee: str, value: dict) -> None:
	ttl = max(int(value["expires_at"] - time.time()), 1)
	frappe.cache.set_value(otp_key(employee), value, expires_in_sec=ttl)


def hash_otp(employee: str, otp: str) -> str:
	return hashlib.sha256(f"{employee}:{otp}".encode()).hexdigest()


def mask_email(email: str) -> str:
	local, _at, domain = email.partition("@")
	return f"{local[:2]}{'*' * max(len(local) - 2, 3)}@{domain}"


def otp_key(employee: str) -> str:
	return f"centhr_web_form_otp::{employee}"


def token_key(token: str) -> str:
	return f"centhr_web_form_otp_token::{token}"
