# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from centhr.api.migrate.base import Migrator, get_overlap_filters
from centhr.api.migrate.client import MigrationError
from centhr.api.migrate.leave_policy import get_local_policies


class LeavePolicyAssignmentMigrator(Migrator):
	"""On submit, HRMS creates the Leave Allocations of the policy here by itself."""

	doctype = "Leave Policy Assignment"
	list_fields = ("employee", "employee_name", "leave_policy", "effective_from", "effective_to", "docstatus")
	duplicate_fields = ("employee", "leave_policy", "effective_from")
	# Set by the submit here; copied as 1, HRMS refuses to allocate the leaves
	cleared_fields = ("leaves_allocated",)

	def __init__(self, company: str):
		super().__init__(company)
		# Leave Policy of the CentHR site -> the one migrated for this company, None if not migrated
		self.policies = {}

	def get_section_filters(self, filters: frappe._dict) -> list:
		return get_overlap_filters(filters, "effective_from", "effective_to")

	def get_existing_names(self, rows: list[dict]) -> dict[str, str]:
		self.load_policies([row.get("leave_policy") for row in rows])
		return super().get_existing_names(rows)

	def get_key(self, row: dict) -> tuple | None:
		return super().get_key({**row, "leave_policy": self.get_local_policy(row.get("leave_policy"))})

	def get_local_link(self, doctype: str, value: str) -> str | None:
		if doctype != "Leave Policy":
			return super().get_local_link(doctype, value)

		# Another company's policy can have the same name here, so never match by name
		local = self.get_local_policy(value)
		if not local:
			message = _("Leave Policy {0} of {1} has not been migrated. Migrate it in the Leave Policy tab first.")
			raise MigrationError(message.format(value, self.company))
		return local

	def get_local_policy(self, remote_policy: str | None) -> str | None:
		if not remote_policy:
			return None
		self.load_policies([remote_policy])
		return self.policies[remote_policy]

	def load_policies(self, remote_policies: list[str]) -> None:
		missing = list({policy for policy in remote_policies if policy and policy not in self.policies})
		if missing:
			local = get_local_policies(self.company, missing)
			self.policies.update({policy: local.get(policy) for policy in missing})


def migrate(company: str, name: str) -> frappe._dict:
	return LeavePolicyAssignmentMigrator(company).migrate(name)
