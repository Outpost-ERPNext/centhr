import frappe
from frappe import _

# The buttons of the Desk Holiday List form; they change the holidays table without saving
TABLE_METHODS = ("get_weekly_off_dates", "get_local_holidays", "clear_table")


@frappe.whitelist(methods=["POST"])
def update_holidays(doc: dict | str, method: str) -> dict:
	"""Runs a Holiday List table button on the unsaved form values and returns the new table.
	The user saves the list afterwards, as in Desk."""
	if method not in TABLE_METHODS:
		frappe.throw(_("{0} is not a Holiday List action").format(method))

	doc = frappe.get_doc(frappe.parse_json(doc))
	if doc.doctype != "Holiday List":
		frappe.throw(_("Only Holiday Lists can be updated here"))
	doc.check_permission("create" if doc.is_new() else "write")

	doc.run_method(method)
	return {
		"holidays": [row.as_dict(convert_dates_to_str=True) for row in doc.holidays],
		"total_holidays": doc.total_holidays,
	}


@frappe.whitelist()
def get_supported_countries() -> dict:
	"""Countries and their subdivisions for the Country and Subdivision pickers, as in the Desk form."""
	if not frappe.has_permission("Holiday List", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return frappe.new_doc("Holiday List").get_supported_countries()


@frappe.whitelist()
def get_active_holiday_list(company: str, exclude: str | None = None) -> str | None:
	"""The company's active holiday list, other than `exclude`; the forms name it in their confirmation."""
	if not frappe.has_permission("Holiday List", "read"):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	filters = {"company": company, "is_active": 1}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.db.get_value("Holiday List", filters, "name")


def validate_active(doc, method=None):
	if doc.is_active and not doc.company:
		frappe.throw(_("Set a Company before you make this holiday list active"))


def apply_active_list(doc, method=None):
	"""Holiday List on_update. Only one list per company is active: activating one deactivates the
	others, and the active list is set on every employee of that company."""
	if not doc.is_active:
		return
	others = frappe.get_all(
		"Holiday List", filters={"company": doc.company, "is_active": 1, "name": ("!=", doc.name)}, pluck="name"
	)
	for name in others:
		frappe.db.set_value("Holiday List", name, "is_active", 0)

	employees = frappe.get_all(
		"Employee",
		filters={"company": doc.company},
		or_filters=[["holiday_list", "is", "not set"], ["holiday_list", "!=", doc.name]],
		pluck="name",
	)
	if employees:
		# One update for the whole company; Employee save hooks do not run
		employee = frappe.qb.DocType("Employee")
		frappe.qb.update(employee).set(employee.holiday_list, doc.name).set(
			employee.modified, frappe.utils.now()
		).where(employee.name.isin(employees)).run()

	messages = []
	if others:
		messages.append(_("Deactivated {0}.").format(", ".join(others)))
	if employees:
		messages.append(
			_("{0} is now the holiday list of {1} employees of {2}.").format(doc.name, len(employees), doc.company)
		)
	if messages:
		frappe.msgprint(" ".join(messages), alert=True)


def set_employee_holiday_list(doc, method=None):
	"""Employee validate: the employee follows their company's active holiday list."""
	if not doc.company:
		return
	active = frappe.db.get_value("Holiday List", {"company": doc.company, "is_active": 1}, "name")
	if active and doc.holiday_list != active:
		doc.holiday_list = active
