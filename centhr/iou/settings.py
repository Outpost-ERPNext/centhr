"""The IOU tab of CentHr Settings."""

import frappe
from frappe import _

SETTINGS = "CentHr Settings"

DEFAULTS = {
	"iou_travel_grace_days": 7,
	"iou_other_due_days": 5,
	"iou_due_reminder_days": 3,
	"iou_payroll_notice_days": 7,
	"iou_payroll_day": 0,
	"iou_escalation_hours": 24,
}


def get_value(fieldname: str):
	return frappe.db.get_single_value(SETTINGS, fieldname)


def get_int(fieldname: str) -> int:
	# An Int field that was never set reads as 0, so 0 falls back to the SOP default
	value = get_value(fieldname)
	return int(value) if value else DEFAULTS[fieldname]


def finance_1() -> str | None:
	return get_value("iou_finance_1")


def finance_2() -> str | None:
	return get_value("iou_finance_2")


def salary_component() -> str:
	component = get_value("iou_salary_component")
	if not component:
		frappe.throw(_("Set the IOU Recovery Salary Component in CentHr Settings."), title=_("IOU Settings"))
	return component


def proxy_for(user: str | None) -> str | None:
	if not user:
		return None
	return frappe.db.get_value("IOU Proxy", {"parenttype": SETTINGS, "approver": user}, "proxy")


def full_name(user: str | None) -> str:
	if not user:
		return ""
	return frappe.db.get_value("User", user, "full_name") or user
