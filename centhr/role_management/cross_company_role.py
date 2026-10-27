import frappe
from frappe.permissions import add_user_permission, remove_user_permission


def sync_cross_company_permissions(doc, method=None):
	"""Give the cross-company Reports To manager's user access to this employee and their company."""
	old = doc.get_doc_before_save()
	old_user = _cross_manager_user(old)
	new_user = _cross_manager_user(doc)

	if old_user and (old_user, old.company) != (new_user, doc.company):
		_revoke_cross_company_permissions(doc.name, old.company, old_user)
	# re-run on every save: it only adds what is missing
	if new_user:
		_grant_cross_company_permissions(doc, new_user)


def remove_cross_company_permissions(doc, method=None):
	user = _cross_manager_user(doc)
	if user:
		_revoke_cross_company_permissions(doc.name, doc.company, user)


def _cross_manager_user(doc):
	if doc and doc.cross_company_reports and doc.reports_to:
		return frappe.db.get_value("Employee", doc.reports_to, "user_id")


def _grant_cross_company_permissions(doc, user):
	"""Add access to the employee's company without narrowing what the user could already see:
	a User Permission also hides every value of that DocType not listed for the user."""
	manager_company = frappe.db.get_value("Employee", doc.reports_to, "company")

	if not _has_permission(user, "Company"):
		# the first Company permission would hide the manager's own company
		add_user_permission("Company", manager_company, user, ignore_permissions=True, is_default=1)
	add_user_permission("Company", doc.company, user, ignore_permissions=True)

	# without an Employee restriction the Company permission already shows this employee;
	# adding one would hide every other employee
	if _has_permission(user, "Employee"):
		add_user_permission("Employee", doc.name, user, ignore_permissions=True)


def _has_permission(user, doctype):
	return bool(frappe.db.exists("User Permission", {"user": user, "allow": doctype}))


def _revoke_cross_company_permissions(employee, company, user):
	_remove_permission("Employee", employee, user)

	# keep the Company permission while it is the manager's own company
	# or another cross-company employee of that company still reports to them
	if frappe.db.exists("Employee", {"user_id": user, "company": company}):
		return
	managers = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
	still_needed = frappe.db.exists(
		"Employee",
		{
			"name": ("!=", employee),
			"company": company,
			"cross_company_reports": 1,
			"reports_to": ("in", managers),
		},
	)
	if not still_needed:
		_remove_permission("Company", company, user)


def _remove_permission(doctype, value, user):
	if frappe.db.exists("User Permission", {"user": user, "allow": doctype, "for_value": value}):
		remove_user_permission(doctype, value, user, ignore_permissions=True)
