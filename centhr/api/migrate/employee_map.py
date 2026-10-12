# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import frappe

from centhr.api.migrate.client import TargetClient

CHUNK_SIZE = 200


class EmployeeMap:
	"""Match employees of the CentHR site to employees of this site by employee_number.

	This is the same key that the push sync in centhr/api/post uses, in the other direction.
	"""

	def __init__(self, client: TargetClient):
		self.client = client
		self.local_by_remote = {}

	def get_local(self, remote_employee: str) -> str | None:
		self.load([remote_employee])
		return self.local_by_remote.get(remote_employee)

	def load(self, remote_employees: list[str]) -> None:
		missing = list({name for name in remote_employees if name and name not in self.local_by_remote})
		for start in range(0, len(missing), CHUNK_SIZE):
			self.load_chunk(missing[start : start + CHUNK_SIZE])

	def load_chunk(self, remote_employees: list[str]) -> None:
		remote_rows = self.client.get_all(
			"Employee", [["name", "in", remote_employees]], ["name", "employee_number"]
		)
		number_by_remote = {row["name"]: row.get("employee_number") or row["name"] for row in remote_rows}
		local_by_number = get_local_employees(list(number_by_remote.values()))

		for remote in remote_employees:
			self.local_by_remote[remote] = local_by_number.get(number_by_remote.get(remote))

	def get_remote(self, local_employee: str) -> str | None:
		employee_number = (
			frappe.db.get_value("Employee", local_employee, "employee_number") or local_employee
		)
		rows = self.client.get_all("Employee", [["employee_number", "=", employee_number]], ["name"])
		return rows[0]["name"] if rows else None


def get_local_employees(employee_numbers: list[str]) -> dict[str, str]:
	"""Map each employee_number to a local Employee.

	The push sync sends the Employee name when employee_number is empty, so the name is a match too.
	"""
	if not employee_numbers:
		return {}

	by_number = dict(
		frappe.get_all(
			"Employee",
			filters={"employee_number": ["in", employee_numbers]},
			fields=["employee_number", "name"],
			as_list=True,
		)
	)
	unmatched = [number for number in employee_numbers if number not in by_number]
	if unmatched:
		by_name = frappe.get_all(
			"Employee",
			filters={"name": ["in", unmatched], "employee_number": ["is", "not set"]},
			pluck="name",
		)
		by_number.update({name: name for name in by_name})
	return by_number
