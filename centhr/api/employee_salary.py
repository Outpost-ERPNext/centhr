import frappe
from frappe import _
from frappe.utils import flt, get_link_to_form

SSA = "Salary Structure Assignment"
SALARY_FIELDS = ("salary_structure", "employee_base", "from_date", "payroll_payable_account")


def sync_salary_structure_assignment(doc, method=None):
	"""Keeps one submitted Salary Structure Assignment in line with the employee's salary fields."""
	if doc.status != "Active" or not all(doc.get(f) for f in SALARY_FIELDS):
		return

	existing = frappe.db.get_value(
		SSA,
		{"employee": doc.name, "from_date": doc.from_date, "docstatus": 1},
		["name", "salary_structure", "base", "payroll_payable_account"],
		as_dict=True,
	)
	if existing and is_same(existing, doc):
		return
	if existing:
		# A submitted assignment cannot be edited, so it is replaced
		frappe.get_doc(SSA, existing.name).cancel()

	assignment = make_assignment(doc)
	frappe.msgprint(
		_("Salary Structure Assignment {0} created").format(get_link_to_form(SSA, assignment.name)),
		alert=True,
	)


def is_same(existing, doc) -> bool:
	return (
		existing.salary_structure == doc.salary_structure
		and flt(existing.base) == flt(doc.employee_base)
		and existing.payroll_payable_account == doc.payroll_payable_account
	)


def make_assignment(doc):
	# The Employee save has passed its permission check; HR may not have rights on the assignment
	assignment = frappe.get_doc(
		{
			"doctype": SSA,
			"employee": doc.name,
			"company": doc.company,
			"salary_structure": doc.salary_structure,
			"from_date": doc.from_date,
			"base": doc.employee_base,
			"payroll_payable_account": doc.payroll_payable_account,
			"currency": frappe.db.get_value("Salary Structure", doc.salary_structure, "currency"),
		}
	)
	assignment.insert(ignore_permissions=True)
	assignment.submit()
	return assignment
