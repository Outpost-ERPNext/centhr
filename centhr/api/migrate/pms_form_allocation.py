# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.pms_base import PmsMigrator, find_local

RELATIONSHIPS = {
	"Line Manager": "Line Manager",
	"Superior": "Line Manager",
	"Peers": "Peers",
	"Peer": "Peers",
}


class PmsFormAllocationMigrator(PmsMigrator):
	"""One review that was asked for. Its PMS Questionnaire must be migrated first. It shows as Pending
	until its review is migrated in the PMS Question Form tab."""

	doctype = "PMS Form Allocation"
	list_fields = (
		"reviewee",
		"reviewee_name",
		"reviewer",
		"reviewer_name",
		"relationship_type",
		"fiscal_year",
		"quarter",
	)
	duplicate_fields = ("reviewer", "reviewee", "fiscal_year", "quarter")
	employee_fields = ("reviewer", "reviewee")
	title_field = "reviewee_name"
	remote_filter_fields = ("fiscal_year", "quarter")

	def prepare(self, remote: dict) -> dict:
		relationship = RELATIONSHIPS.get(remote.get("relationship_type") or "")
		if not relationship:
			raise MigrationError(
				_("Its relationship {0} is not a line manager or peer review.").format(
					remote.get("relationship_type") or _("(empty)")
				)
			)
		reviewee = self.local_employee(remote.get("reviewee"), _("Reviewee"))
		fiscal_year = remote.get("fiscal_year")
		quarter = remote.get("quarter") or self.get_remote_questionnaire(remote.get("form_reference")).quarter
		questionnaire = find_local(
			"PMS Questionnaire", employee=reviewee, fiscal_year=fiscal_year, quarter=quarter
		)
		if not questionnaire:
			raise MigrationError(
				_(
					"{0} has no PMS Questionnaire for {1} {2} here. Migrate it in the PMS Questionnaire tab first."
				).format(remote.get("reviewee_name") or reviewee, quarter, fiscal_year)
			)
		return {
			"reviewer": self.local_employee(remote.get("reviewer"), _("Reviewer")),
			"reviewee": reviewee,
			"relationship_type": relationship,
			"fiscal_year": fiscal_year,
			"quarter": quarter,
			"form_reference": questionnaire,
		}


def migrate(company: str, name: str) -> frappe._dict:
	return PmsFormAllocationMigrator(company).migrate(name)
