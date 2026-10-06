# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import json

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model import no_value_fields, table_fields
from frappe.utils import get_request_session

EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_employee_sync(doc, method=None):
	if not get_targets(doc.company):
		return

	frappe.enqueue(
		"centhr.api.post.employee.sync_employee",
		queue="short",
		job_id=f"centhr_employee_sync::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		employee=doc.name,
	)


def sync_employee(employee: str) -> None:
	doc = frappe.get_doc("Employee", employee)
	payload = build_payload(doc)
	failed_targets = []

	for target in get_targets(doc.company):
		try:
			sync_to_target(doc, payload, target)
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
	payload["employee_number"] = doc.employee_number or doc.name
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


def sync_to_target(doc, payload: dict, target) -> None:
	url = target.base_url.rstrip("/") + EMPLOYEE_ENDPOINT
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	if find_target_employee(doc, target, url, headers, payload["employee_number"]):
		return

	send_request(doc, target, "POST", url, headers, json=payload)


def find_target_employee(doc, target, url: str, headers: dict, employee_number: str) -> str | None:
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps([["employee_number", "=", employee_number]]),
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

	if method == "POST" and response is not None and response.status_code == 409:
		insert_log(
			doc,
			target,
			status="Success",
			error=_("Employee already exists in the target system"),
			**log_fields,
		)
		return {}

	if error:
		insert_log(doc, target, status="Failed", error=error, **log_fields)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Sync Failed"))

	if method == "POST":
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
	if status == 409:
		return _("HTTP 409: Employee already exists in the target system")
	if status in (400, 417, 422):
		return _("HTTP {0}: the target rejected the Employee data. {1}").format(
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
			"doctypes": "Employee",
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
			"document_type": "Employee",
			"document_name": doc.name,
			"subject": _("CentHR sync of Employee {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
