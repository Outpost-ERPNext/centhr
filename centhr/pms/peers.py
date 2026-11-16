"""Peer mapping: the up to two colleagues who review an employee in the 360 review."""

import frappe
from frappe.utils import getdate, today

MAPPING = "PMS Employee Relationship"
MAX_PEERS = 2
# Days of the month the scheduler refreshes every company's mappings
REFRESH_DAYS = (1, 16)


class PeerMapping:
	"""Gives every active employee of a company who has a department a mapping, and keeps it current:
	peers who left or who became the line manager are dropped, and free places are filled.
	Mappings that HR locked are left alone."""

	def __init__(self, company: str):
		self.company = company
		self.employees = frappe.get_all(
			"Employee",
			filters={"company": company, "status": "Active", "department": ["is", "set"]},
			fields=["name", "department", "grade", "reports_to"],
			order_by="name asc",
		)
		self.active = {employee.name for employee in self.employees}
		self.lower_grade = get_lower_grades(company)
		self.stats = frappe._dict(
			employees=len(self.employees), created=0, locked=0, peers_added=0, peers_removed=0
		)

	def run(self) -> dict:
		for employee in self.employees:
			self.refresh(employee)
		return self.stats

	def refresh(self, employee) -> None:
		mapping = self.get_mapping(employee.name)
		if mapping.locked:
			self.stats.locked += 1
			return

		kept = [
			row
			for row in mapping.peers
			if row.employee in self.active and row.employee != employee.reports_to
		]
		kept = kept[:MAX_PEERS]
		added = self.find_peers(employee, exclude={row.employee for row in kept}, count=MAX_PEERS - len(kept))
		if not mapping.is_new() and len(kept) == len(mapping.peers) and not added:
			return

		self.stats.peers_removed += len(mapping.peers) - len(kept)
		self.stats.peers_added += len(added)
		self.stats.created += int(mapping.is_new())
		mapping.set(
			"peers", [{"employee": row.employee} for row in kept] + [{"employee": name} for name in added]
		)
		mapping.flags.skip_reverse_mapping = True
		mapping.save(ignore_permissions=True)

	def get_mapping(self, employee: str):
		if frappe.db.exists(MAPPING, employee):
			return frappe.get_doc(MAPPING, employee)
		return frappe.get_doc({"doctype": MAPPING, "employee": employee})

	def find_peers(self, employee, exclude: set[str], count: int) -> list[str]:
		"""The closest colleagues first: same department, grade and line manager; then same department
		and grade; then the same department one grade lower."""
		if count <= 0:
			return []

		exclude = {*exclude, employee.name, employee.reports_to}
		in_department = [
			e for e in self.employees if e.department == employee.department and e.name not in exclude
		]
		same_grade = [e for e in in_department if e.grade == employee.grade]
		tiers = [
			[e for e in same_grade if employee.reports_to and e.reports_to == employee.reports_to],
			same_grade,
			[e for e in in_department if e.grade and e.grade == self.lower_grade.get(employee.grade)],
		]

		found = []
		for tier in tiers:
			found += [e.name for e in tier if e.name not in found]
		return found[:count]


def add_reverse_mappings(mapping) -> None:
	"""Peers review each other: when HR makes John a peer of Harry, Harry becomes a peer of John too,
	as long as John has a free place and his mapping is not locked."""
	for row in mapping.peers:
		if frappe.db.exists(MAPPING, row.employee):
			other = frappe.get_doc(MAPPING, row.employee)
		else:
			other = frappe.get_doc({"doctype": MAPPING, "employee": row.employee})

		listed = {peer.employee for peer in other.peers}
		line_manager = frappe.db.get_value("Employee", row.employee, "reports_to")
		if (
			other.locked
			or mapping.employee in listed
			or len(listed) >= MAX_PEERS
			or mapping.employee == line_manager
		):
			continue
		other.append("peers", {"employee": mapping.employee})
		other.flags.skip_reverse_mapping = True
		other.save(ignore_permissions=True)


def get_lower_grades(company: str) -> dict[str, str]:
	"""Each grade and the one below it, from the Grade Levels of the company's PMS Settings."""
	levels = frappe.get_all(
		"PMS Grade Level",
		filters={"parent": company, "parenttype": "PMS Settings"},
		pluck="grade",
		order_by="idx asc",
	)
	return dict(zip(levels[1:], levels, strict=False))


def refresh_all_companies() -> None:
	"""Scheduled daily; works on the 1st and 16th, for every company that has PMS Settings."""
	if getdate(today()).day not in REFRESH_DAYS:
		return
	for company in frappe.get_all("PMS Settings", pluck="company"):
		try:
			PeerMapping(company).run()
			frappe.db.commit()
		except Exception:
			# One company's bad record must not stop the others
			frappe.db.rollback()
			frappe.log_error(title=f"Peer mapping of {company} failed")
