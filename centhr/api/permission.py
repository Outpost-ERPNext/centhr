import frappe

HR_ROLES = {"HR User", "HR Manager", "System Manager"}


def has_app_permission():
	"""Show CentHR on the apps screen to HR staff and to users linked to an Employee."""
	if frappe.session.user == "Administrator":
		return True
	if HR_ROLES.intersection(frappe.get_roles()):
		return True
	return bool(frappe.db.exists("Employee", {"user_id": frappe.session.user, "status": "Active"}))


PTYPES = ("read", "write", "create", "submit", "cancel", "delete")


@frappe.whitelist()
def get_doctype_permissions(doctypes: list[str] | str) -> dict:
	"""DocType-level permissions, so the CentHR UI can hide actions the user cannot take.
	The server still checks every write."""
	doctypes = frappe.parse_json(doctypes) if isinstance(doctypes, str) else doctypes
	return {
		doctype: {ptype: bool(frappe.has_permission(doctype, ptype)) for ptype in PTYPES}
		for doctype in doctypes
		if frappe.db.exists("DocType", doctype)
	}


@frappe.whitelist()
def get_readable_fields(doctype: str) -> list[str]:
	"""Fields the session user may read after field-level (permlevel) permissions, so list
	queries ask only for those. The server still checks every query."""
	if not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_meta(doctype).get_permitted_fieldnames(permission_type="read")
