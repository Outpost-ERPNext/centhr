# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.pms_base import PmsMigrator, find_local

ALLOCATION = "PMS Form Allocation"
KEPT_FIELDS = ("review_date", "remarks", "average_rating", "rating_score", "superior_weight", "peers_weight")


class PmsQuestionFormMigrator(PmsMigrator):
	"""One review that was given. Its PMS Form Allocation must be migrated first. The ratings, the score
	and the weights are kept as they were on the CentHR site, and the allocation is marked Completed."""

	doctype = "PMS Question Form"
	list_fields = (
		"reviewee_name",
		"reviewer_name",
		"relationship_type",
		"fiscal_year",
		"average_rating",
		"rating_score",
	)
	# One review per allocation here, see find_existing
	duplicate_fields = ()
	employee_fields = ()
	title_field = "reviewee_name"
	remote_filter_fields = ("fiscal_year",)

	def prepare(self, remote: dict) -> dict:
		allocation = self.get_local_allocation(remote)
		details = frappe.db.get_value(
			ALLOCATION,
			allocation,
			[
				"reviewer",
				"reviewee",
				"relationship_type",
				"fiscal_year",
				"quarter",
				"company",
				"department",
				"form_reference",
			],
			as_dict=True,
		)
		return {
			"pms_form_allocation": allocation,
			"pms_questionnaire": details.pop("form_reference"),
			**details,
			**{field: remote.get(field) for field in KEPT_FIELDS},
			"pms_questionnaire_list": [
				{"question": row.get("question"), "rating": row.get("rating"), "remarks": row.get("remarks")}
				for row in remote.get("pms_questionnaire_list") or []
			],
		}

	def get_local_allocation(self, remote: dict) -> str:
		"""The allocation here for the same reviewer, reviewee and quarter as the review's on the CentHR site."""
		if not remote.get("pms_form_allocation"):
			raise MigrationError(
				_("It has no PMS Form Allocation, so its reviewer and quarter are not known.")
			)
		asked = self.client.get_doc(ALLOCATION, remote["pms_form_allocation"])
		about = {
			"reviewer": self.local_employee(asked.get("reviewer"), _("Reviewer")),
			"reviewee": self.local_employee(asked.get("reviewee"), _("Reviewee")),
			"fiscal_year": asked.get("fiscal_year"),
			"quarter": asked.get("quarter")
			or self.get_remote_questionnaire(asked.get("form_reference")).quarter,
		}
		allocation = find_local(ALLOCATION, **about, docstatus=1)
		if not allocation:
			raise MigrationError(
				_(
					"The review of {0} by {1} for {2} {3} is not asked for here. Migrate it in the PMS Form Allocation tab first."
				).format(
					asked.get("reviewee_name") or about["reviewee"],
					asked.get("reviewer_name") or about["reviewer"],
					about["quarter"],
					about["fiscal_year"],
				)
			)
		return allocation

	def find_existing(self, values: dict) -> str | None:
		return find_local(self.doctype, pms_form_allocation=values["pms_form_allocation"])

	def after_create(self, doc) -> None:
		# The DocType does this itself for a review given here; a migrated one skips its own checks
		if doc.docstatus == 1:
			frappe.db.set_value(
				ALLOCATION, doc.pms_form_allocation, {"status": "Completed", "review_date": doc.review_date}
			)


def migrate(company: str, name: str) -> frappe._dict:
	return PmsQuestionFormMigrator(company).migrate(name)
