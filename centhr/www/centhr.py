import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/centhr"
		raise frappe.Redirect

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	context.boot = {"csrf_token": csrf_token, "user": frappe.session.user}
