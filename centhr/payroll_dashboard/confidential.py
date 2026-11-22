"""Confidential salary structures: who may see the employees they pay, and which payroll batch pays them.

The rules are Payroll Structure Rule documents. A user without a rule's role does not see that
structure's salary structure assignments, salary slips or payroll entries anywhere: the conditions
below are permission hooks, so lists, reports and every tab of the Payroll Dashboard follow them."""

import frappe

RULE = "Payroll Structure Rule"
STANDARD_BATCHES = ("Regular", "Exited")
SEE_ALL_ROLE = "System Manager"


def get_rules(company: str | None = None) -> list:
	return frappe.get_all(
		RULE,
		filters={"confidential": 1, "disabled": 0, **({"company": company} if company else {})},
		fields=["salary_structure", "allowed_role", "batch_name", "company"],
	)


def get_batch_of(company: str | None = None) -> dict[str, str]:
	"""Confidential salary structure -> the batch that pays it."""
	return {rule.salary_structure: rule.batch_name for rule in get_rules(company)}


def may_see(rule, user: str | None = None) -> bool:
	return bool({rule.allowed_role, SEE_ALL_ROLE}.intersection(frappe.get_roles(user)))


def get_hidden_structures(user: str | None = None) -> list[str]:
	return [rule.salary_structure for rule in get_rules() if not may_see(rule, user)]


def get_hidden_batches(user: str | None = None) -> list[tuple[str, str]]:
	"""(company, batch) of the payroll entries the user may not see."""
	return [(rule.company, rule.batch_name) for rule in get_rules() if not may_see(rule, user)]


def get_visible_batches(company: str) -> dict[str, str]:
	"""Confidential structure -> batch, for the batches the user may generate and see."""
	return {rule.salary_structure: rule.batch_name for rule in get_rules(company) if may_see(rule)}


def check_may_use(company: str, batch: str) -> None:
	"""Only those who may see a confidential batch may generate it."""
	if batch in STANDARD_BATCHES:
		return
	if batch not in get_visible_batches(company).values():
		frappe.throw(
			frappe._("Payroll batch {0} does not exist for {1}, or you may not run it.").format(
				batch, company
			),
			frappe.PermissionError,
		)


def get_hidden_employees(employees: list[str], as_on) -> set[str]:
	"""Employees whose salary structure, as assigned by `as_on`, is hidden from the user."""
	hidden = get_hidden_structures()
	if not hidden or not employees:
		return set()
	latest = {}
	for row in frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": ["in", employees], "docstatus": 1, "from_date": ["<=", as_on]},
		fields=["employee", "salary_structure"],
		order_by="from_date asc",
	):
		latest[row.employee] = row.salary_structure
	own = get_own_employee()
	return {employee for employee, structure in latest.items() if structure in hidden and employee != own}


# Permission hooks


def get_structure_conditions(user: str | None = None, doctype: str = "Salary Slip") -> str:
	"""Salary Slip and Salary Structure Assignment lists leave out hidden structures. Employees still
	see their own records."""
	hidden = get_hidden_structures(user)
	if not hidden:
		return ""
	table = f"`tab{doctype}`"
	structures = ", ".join(frappe.db.escape(name) for name in hidden)
	condition = f"ifnull({table}.salary_structure, '') not in ({structures})"
	own = get_own_employee(user)
	return f"({condition} or {table}.employee = {frappe.db.escape(own)})" if own else condition


def get_assignment_conditions(user: str | None = None) -> str:
	return get_structure_conditions(user, "Salary Structure Assignment")


def has_structure_permission(doc, ptype=None, user=None) -> bool:
	if doc.get("salary_structure") not in get_hidden_structures(user):
		return True
	return doc.get("employee") == get_own_employee(user)


def get_entry_conditions(user: str | None = None) -> str:
	hidden = get_hidden_batches(user)
	if not hidden:
		return ""
	pairs = ", ".join(
		f"({frappe.db.escape(company)}, {frappe.db.escape(batch)})" for company, batch in hidden
	)
	return (
		f"(`tabPayroll Entry`.company, ifnull(`tabPayroll Entry`.centhr_batch, 'Regular')) not in ({pairs})"
	)


def has_entry_permission(doc, ptype=None, user=None) -> bool:
	return (doc.company, doc.get("centhr_batch") or "Regular") not in get_hidden_batches(user)


def get_own_employee(user: str | None = None) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": user or frappe.session.user}, "name")
