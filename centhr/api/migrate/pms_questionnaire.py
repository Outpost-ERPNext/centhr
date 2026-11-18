# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.pms_base import PmsMigrator, get_quarter


class PmsQuestionnaireMigrator(PmsMigrator):
	"""An employee's questionnaire of a quarter, with its questions. Closed questionnaires stay closed;
	their reviewers are migrated in the PMS Form Allocation tab, not asked again."""

	doctype = "PMS Questionnaire"
	list_fields = ("employee", "employee_name", "department", "fiscal_year", "quarter", "status")
	duplicate_fields = ("employee", "fiscal_year", "quarter")
	remote_filter_fields = ("fiscal_year", "quarter")

	def prepare(self, remote: dict) -> dict:
		values = super().prepare(remote)
		values["quarter"] = get_quarter(remote)
		# "HOD Closed" was a step before Completed that this site does not have
		values["status"] = "Completed" if remote.get("status") == "Completed" else "Open"
		return values


def migrate(company: str, name: str) -> frappe._dict:
	return PmsQuestionnaireMigrator(company).migrate(name)
