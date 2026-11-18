# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.pms_base import PmsMigrator


class PmsQuestionMigrator(PmsMigrator):
	"""The question bank. A question gets the next QTN number of this site; it is the same question
	when its text, department and designation are the same."""

	doctype = "PMS Question"
	list_fields = ("question", "department", "designation", "is_a_general_question")
	duplicate_fields = ("question", "department", "designation")
	employee_fields = ()
	title_field = "question"


def migrate(company: str, name: str) -> frappe._dict:
	return PmsQuestionMigrator(company).migrate(name)
