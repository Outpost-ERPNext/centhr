# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from centhr.api.migrate.pms_base import PmsMigrator, find_local

KEPT_FIELDS = (
	"calculated_score",
	"check_normalized_score",
	"normalized_score",
	"increment",
	"effective_date",
	"old_ctc",
	"new_ctc",
	"ctc_impact",
	"remarks",
)


class PmsScoreSheetMigrator(PmsMigrator):
	"""A score sheet as it was decided on the CentHR site: the increment and CTC are kept, not worked
	out again. Its quarter comes from its PMS Questionnaire there."""

	doctype = "PMS Score Sheet"
	list_fields = ("employee", "employee_name", "calculated_score", "increment", "docstatus")
	# The quarter is only known from the questionnaire, see find_existing
	duplicate_fields = ()
	employee_fields = ()

	def prepare(self, remote: dict) -> dict:
		employee = self.local_employee(remote.get("employee"), frappe._("Employee"))
		period = self.get_remote_questionnaire(remote.get("pms_questionnaire"))
		about = {"employee": employee, "fiscal_year": period.fiscal_year, "quarter": period.quarter}
		return {
			**about,
			**{field: remote.get(field) for field in KEPT_FIELDS},
			"pms_questionnaire": find_local("PMS Questionnaire", **about),
			"currency": frappe.db.get_value("Currency", remote.get("currency"), "name")
			if remote.get("currency")
			else None,
			"outcome": "PIP" if remote.get("pip") else "Increment" if flt(remote.get("increment")) else None,
			"status": "Rejected" if remote.get("workflow_state") == "Rejected" else "Pending",
		}

	def find_existing(self, values: dict) -> str | None:
		about = {field: values[field] for field in ("employee", "fiscal_year", "quarter")}
		return find_local(self.doctype, **about)


def migrate(company: str, name: str) -> frappe._dict:
	return PmsScoreSheetMigrator(company).migrate(name)
