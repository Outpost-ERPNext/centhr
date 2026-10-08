# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model import no_value_fields, table_fields
from frappe.utils import get_request_session

ATTENDANCE_ENDPOINT = "/api/resource/Attendance"
EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REFERENCE_FIELDS = ("leave_application", "attendance_request", "amended_from")
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_attendance_update(doc, method=None):
	if doc.flags.in_insert or doc.docstatus != 0 or not get_targets(doc.company):
		return

	doc_before_save = doc.get_doc_before_save() or doc

	frappe.enqueue(
		"centhr.api.update.attendance.update_attendance",
		queue="short",
		job_id=f"centhr_attendance_update::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		attendance=doc.name,
		employee=doc_before_save.employee,
		attendance_date=str(doc_before_save.attendance_date),
	)


def update_attendance(
	attendance: str, employee: str | None = None, attendance_date: str | None = None
) -> None:
	doc = frappe.get_doc("Attendance", attendance)
	if doc.docstatus != 0:
		return

	payload = build_payload(doc)
	lookup = {
		"employee": employee or doc.employee,
		"attendance_date": attendance_date or payload["attendance_date"],
	}
	failed_targets = []

	for target in get_targets(doc.company):
		try:
			sync_to_target(doc, payload, target, lookup)
		except CentHRSyncError:
			failed_targets.append(target.base_url)
		except Exception as e:
			insert_log(doc, target, status="Failed", error=f"{type(e).__name__}: {e}")
			failed_targets.append(target.base_url)

	if failed_targets:
		notify_failure(doc, failed_targets)


def get_targets(company: str) -> list:
	settings = frappe.get_cached_doc("CentHr Settings")
	return [row for row in settings.authorization if row.company == company]


def build_payload(doc) -> dict:
	payload = get_field_values(doc)
	for fieldname in REFERENCE_FIELDS:
		payload[fieldname] = ""

	payload["docstatus"] = 0
	return frappe.parse_json(frappe.as_json(payload))


def get_field_values(doc) -> dict:
	values = {}
	for df in doc.meta.fields:
		if df.fieldtype in table_fields:
			values[df.fieldname] = [get_field_values(row) for row in doc.get(df.fieldname)]
		elif df.fieldtype not in no_value_fields:
			value = doc.get(df.fieldname)
			values[df.fieldname] = "" if value is None else value

	return values


def sync_to_target(doc, payload: dict, target, lookup: dict) -> None:
	base_url = target.base_url.rstrip("/")
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	url = base_url + ATTENDANCE_ENDPOINT
	lookup_employee = get_target_employee(doc, target, base_url, headers, lookup["employee"])
	target_attendance = find_target_attendance(
		doc, target, url, headers, lookup_employee, lookup["attendance_date"]
	)
	if not target_attendance:
		error = _("No draft Attendance for Employee {0} on {1} in the target system").format(
			lookup["employee"], lookup["attendance_date"]
		)
		insert_log(doc, target, status="Failed", error=error)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Update Failed"))

	employee = (
		lookup_employee
		if lookup["employee"] == doc.employee
		else get_target_employee(doc, target, base_url, headers, doc.employee)
	)
	payload = {**payload, "employee": employee}
	send_request(doc, target, "PUT", f"{url}/{target_attendance}", headers, json=payload)


def get_target_employee(doc, target, base_url: str, headers: dict, employee: str) -> str:
	employee_number = frappe.db.get_value("Employee", employee, "employee_number") or employee
	data = send_request(
		doc,
		target,
		"GET",
		base_url + EMPLOYEE_ENDPOINT,
		headers,
		params={
			"filters": json.dumps([["employee_number", "=", employee_number]]),
			"fields": json.dumps(["name"]),
			"limit_page_length": 1,
		},
	)
	if data:
		return data[0]["name"]

	error = _("Employee {0} is not synced to the target system").format(employee_number)
	insert_log(doc, target, status="Failed", error=error)
	frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Update Failed"))


def find_target_attendance(
	doc, target, url: str, headers: dict, employee: str, attendance_date: str
) -> str | None:
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps(
				[
					["employee", "=", employee],
					["attendance_date", "=", attendance_date],
					["docstatus", "=", 0],
				]
			),
			"fields": json.dumps(["name"]),
			"limit_page_length": 1,
		},
	)
	return data[0]["name"] if data else None


def send_request(doc, target, method: str, url: str, headers: dict, **kwargs) -> dict | list:
	log_fields = {"request_method": method, "endpoint": url, "request_payload": kwargs.get("json")}
	response = None

	try:
		response = get_request_session(MAX_RETRIES).request(
			method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
		)
		data, error = parse_response(response)
	except requests.Timeout:
		data, error = None, _("Request timed out after {0} seconds").format(sum(REQUEST_TIMEOUT))
	except requests.ConnectionError:
		data, error = None, _("Could not connect to the target system")
	except requests.RequestException as e:
		data, error = None, f"{type(e).__name__}: {e}"

	if response is not None:
		log_fields.update(http_status=response.status_code, api_response=response.text[:RESPONSE_LOG_LIMIT])

	if error:
		insert_log(doc, target, status="Failed", error=error, **log_fields)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Update Failed"))

	if isinstance(data, dict):
		log_fields["target_reference"] = data.get("name")
	elif data:
		log_fields["target_reference"] = data[0].get("name")

	insert_log(doc, target, status="Success", **log_fields)
	return data


def parse_response(response) -> tuple[dict | list | None, str | None]:
	if not response.ok:
		return None, get_http_error(response)

	try:
		data = response.json()["data"]
	except ValueError, KeyError, TypeError:
		return None, _("Malformed response from the target system")

	return data, None


def get_http_error(response) -> str:
	status = response.status_code
	if status in (401, 403):
		return _(
			"HTTP {0}: authentication failed. Check the API Key and API Secret in CentHr Settings"
		).format(status)
	if status == 404:
		return _("HTTP 404: endpoint not found. Check the Base URL in CentHr Settings")
	if status in (400, 417, 422):
		return _("HTTP {0}: the target rejected the Attendance data. {1}").format(
			status, get_target_message(response)
		)
	if status >= 500:
		return _("HTTP {0}: target server error. {1}").format(status, get_target_message(response))
	return _("HTTP {0}: unexpected response").format(status)


def get_target_message(response) -> str:
	try:
		body = response.json()
	except ValueError:
		return response.text[:500]

	if not isinstance(body, dict):
		return ""
	return body.get("exception") or body.get("exc_type") or ""


def insert_log(doc, target, status: str, error: str | None = None, **fields) -> None:
	if isinstance(fields.get("request_payload"), dict):
		fields["request_payload"] = frappe.as_json(fields["request_payload"])

	frappe.get_doc(
		{
			"doctype": "CentHR API Logger",
			"doctypes": "Attendance",
			"reference_name": doc.name,
			"name1": doc.employee_name,
			"company": target.company,
			"status": status,
			"error": error,
			**fields,
		}
	).insert(ignore_permissions=True)


def notify_failure(doc, failed_targets: list[str]) -> None:
	users = [row.user for row in frappe.get_cached_doc("CentHr Settings").error_alerts]
	if not users:
		return

	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": "Attendance",
			"document_name": doc.name,
			"subject": _("CentHR update of Attendance {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
