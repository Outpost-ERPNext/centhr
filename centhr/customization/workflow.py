import frappe

STATE_STYLES = {"Approved": "Success", "Rejected": "Danger", "Open": ""}


def create_workflow(name: str, doctype: str, states: list[dict], transitions: list[dict]):
	"""Creates an approval workflow once, with any Workflow State and action it needs. Kept as is after that,
	so HR can adjust it in Desk."""
	if frappe.db.exists("Workflow", name):
		return
	for state in {s["state"] for s in states}:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": STATE_STYLES.get(state, "Primary")}
			).insert(ignore_permissions=True)
	for action in {t["action"] for t in transitions}:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": name,
			"document_type": doctype,
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": states,
			"transitions": transitions,
		}
	).insert(ignore_permissions=True)
