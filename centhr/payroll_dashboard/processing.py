"""Payroll Processing tab: the cycle's totals against the last cycle, its payroll entries and salary slips."""

import frappe
from frappe import _

from centhr.api.payroll import get_payroll_runs
from centhr.payroll_dashboard.scope import Scope, totals

SLIP_ACTIONS = ("submit", "recalculate", "delete")


def get_processing(scope: Scope) -> dict:
	slips = scope.get_slips()
	current, previous = totals(slips), totals(scope.previous().get_slips())
	return {
		"totals": current,
		"previous": previous,
		"runs": get_payroll_runs(str(scope.from_date), str(scope.to_date), scope.company),
		"slips": slips,
	}


def update_slips(action: str, names: list[str]) -> dict:
	"""Runs `action` on each draft slip; one failure does not stop the others."""
	if action not in SLIP_ACTIONS:
		frappe.throw(_("Unknown action {0}.").format(action))
	done, failed = [], []
	for name in names:
		frappe.db.savepoint("slip_action")
		try:
			run_slip_action(action, name)
			done.append(name)
		except Exception as e:
			frappe.db.rollback(save_point="slip_action")
			failed.append({"name": name, "error": frappe.utils.strip_html(str(e))})
	frappe.clear_messages()
	return {"done": done, "failed": failed}


def run_slip_action(action: str, name: str):
	doc = frappe.get_doc("Salary Slip", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only draft salary slips can be changed."))
	if action == "delete":
		doc.delete()
	elif action == "submit":
		doc.submit()
	else:
		# Saving a draft slip makes HRMS work its days and amounts out again
		doc.save()
