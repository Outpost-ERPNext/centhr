import frappe
from frappe.utils import get_system_timezone

no_cache = 1


def get_context(context):
	# The SPA shows its own login page, so guests are not redirected here.
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep
	context.boot = {**get_boot(), "csrf_token": csrf_token}


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_context_for_dev():
	"""Boot data for the Vite dev server, which does not render this page."""
	if not frappe.conf.developer_mode:
		frappe.throw(frappe._("This method is only meant for developer mode"))
	return {**get_boot(), "csrf_token": frappe.sessions.get_csrf_token()}


def get_boot():
	return {
		"app_name": "CentHR",
		"site_name": frappe.local.site,
		"user": frappe.session.user,
		"sysdefaults": get_sysdefaults(),
	}


def get_sysdefaults():
	return {
		"date_format": frappe.db.get_default("date_format") or "dd-mm-yyyy",
		"time_format": frappe.db.get_default("time_format") or "HH:mm:ss",
		"number_format": frappe.db.get_default("number_format") or "#,###.##",
		"currency": frappe.db.get_default("currency"),
		"time_zone": get_system_timezone(),
	}
