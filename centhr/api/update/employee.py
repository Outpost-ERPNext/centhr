# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import html
import json
import re

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model import no_value_fields, table_fields
from requests.adapters import HTTPAdapter, Retry

EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000
# Nested set fields of the reports_to tree; the target maintains its own values
EXCLUDED_FIELDS = ("lft", "rgt", "old_parent")


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_employee_update(doc, method=None):
	if doc.flags.in_insert or not get_targets(doc.company):
		return

	doc_before_save = doc.get_doc_before_save()
	employee_number = doc_before_save.employee_number if doc_before_save else doc.employee_number

	frappe.enqueue(
		"centhr.api.update.employee.update_employee",
		queue="short",
		job_id=f"centhr_employee_update::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		employee=doc.name,
		employee_number=employee_number,
	)


def update_employee(employee: str, employee_number: str | None = None) -> None:
	doc = frappe.get_doc("Employee", employee)
	payload = build_payload(doc)
	employee_number = employee_number or payload["employee_number"]
	failed_targets = []

	for target in get_targets(doc.company):
		try:
			sync_to_target(doc, payload, target, employee_number)
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
	for fieldname in EXCLUDED_FIELDS:
		payload.pop(fieldname, None)
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


def sync_to_target(doc, payload: dict, target, employee_number: str) -> None:
	url = target.base_url.rstrip("/") + EMPLOYEE_ENDPOINT
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	target_employee = find_target_employee(doc, target, url, headers, employee_number)
	if not target_employee:
		error = _("Employee {0} is not synced to the target system").format(employee_number)
		insert_log(doc, target, status="Failed", error=error)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Update Failed"))

	send_request(doc, target, "PUT", f"{url}/{target_employee}", headers, json=payload)


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
		response = get_session().request(
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


def get_session() -> requests.Session:
	# Retry connection errors only; a 500 from the target is returned so its error page gets logged
	session = requests.Session()
	session.mount("http://", HTTPAdapter(max_retries=Retry(total=MAX_RETRIES, raise_on_status=False)))
	session.mount("https://", HTTPAdapter(max_retries=Retry(total=MAX_RETRIES, raise_on_status=False)))
	return session


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
		return get_html_error(response.text)

	if not isinstance(body, dict):
		return ""
	return body.get("exception") or body.get("exc_type") or ""


def get_html_error(text: str) -> str:
	# Werkzeug debugger page: keep the title plus every traceback frame, as the page itself is truncated in the log
	title = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
	frames = re.findall(
		r'<cite class="filename">"(.*?)"</cite>,\s*line <em class="line">(\d+)</em>,\s*'
		r'in <code class="function">(.*?)</code>.*?<pre class="line current">(.*?)</pre>',
		text,
		re.DOTALL,
	)
	if not title and not frames:
		return text[:500]

	lines = [title.group(1).strip() if title else ""]
	for filename, lineno, function, code in frames:
		code = html.unescape(re.sub(r"<[^>]+>", "", code)).strip()
		lines.append(f"{filename}:{lineno} in {function}: {code}")
	return "\n".join(lines)


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
			"subject": _("CentHR update of Employee {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
