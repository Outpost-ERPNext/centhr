# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import html
import json
import re
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from requests.adapters import HTTPAdapter, Retry

RESOURCE_ENDPOINT = "/api/resource"
EMPLOYEE_ENDPOINT = RESOURCE_ENDPOINT + "/Employee"
LINKED_DOCS_ENDPOINT = "/api/method/frappe.desk.form.linked_with.get"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000


class CentHRSyncError(frappe.ValidationError):
	def __init__(self, message: str, response_text: str = ""):
		super().__init__(message)
		self.response_text = response_text


def enqueue_employee_delete(doc, method=None):
	if not get_targets(doc.company):
		return

	frappe.enqueue(
		"centhr.api.delete.employee.delete_employee",
		queue="short",
		job_id=f"centhr_employee_delete::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		employee=doc.name,
		employee_name=doc.employee_name,
		employee_number=doc.employee_number or doc.name,
		company=doc.company,
	)


def delete_employee(employee: str, employee_name: str, employee_number: str, company: str) -> None:
	doc = frappe._dict(name=employee, employee_name=employee_name)
	failed_targets = []

	for target in get_targets(company):
		try:
			sync_to_target(doc, target, employee_number)
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


def sync_to_target(doc, target, employee_number: str) -> None:
	url = target.base_url.rstrip("/") + EMPLOYEE_ENDPOINT
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	target_employee = find_target_employee(doc, target, url, headers, employee_number)
	if not target_employee:
		insert_log(
			doc,
			target,
			status="Success",
			error=_("Employee {0} does not exist in the target system").format(employee_number),
		)
		return

	try:
		send_request(doc, target, "DELETE", f"{url}/{target_employee}", headers)
	except CentHRSyncError as e:
		if not is_link_exists_error(e.response_text):
			raise

		# Records on the target still link to the employee: remove them, then delete once more
		remove_linked_records(doc, target, headers, target_employee)
		send_request(doc, target, "DELETE", f"{url}/{target_employee}", headers)


def is_link_exists_error(response_text: str) -> bool:
	return "LinkExistsError" in response_text or "raise_link_exists_exception" in response_text


def remove_linked_records(doc, target, headers: dict, target_employee: str) -> None:
	base_url = target.base_url.rstrip("/")
	linked_docs = send_request(
		doc,
		target,
		"GET",
		base_url + LINKED_DOCS_ENDPOINT,
		headers,
		key="message",
		params={"doctype": "Employee", "docname": target_employee},
	)

	for linked_doctype, records in (linked_docs or {}).items():
		for record in records:
			record_url = f"{base_url}{RESOURCE_ENDPOINT}/{quote(linked_doctype)}/{quote(record['name'])}"

			if linked_doctype == "Employee":
				# Employees reporting to this one are unlinked, never deleted
				send_request(doc, target, "PUT", record_url, headers, json={"reports_to": ""})
				continue

			if record.get("docstatus") == 1:
				send_request(doc, target, "PUT", record_url, headers, json={"docstatus": 2})
			send_request(doc, target, "DELETE", record_url, headers)


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


def send_request(
	doc, target, method: str, url: str, headers: dict, key: str = "data", **kwargs
) -> dict | list | str:
	log_fields = {"request_method": method, "endpoint": url, "request_payload": kwargs.get("json")}
	response = None

	try:
		response = get_session().request(
			method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs
		)
		data, error = parse_response(response, key)
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
		raise CentHRSyncError(error, response.text if response is not None else "")

	if method == "DELETE":
		log_fields["target_reference"] = url.rsplit("/", 1)[-1]
	elif isinstance(data, list) and data:
		log_fields["target_reference"] = data[0].get("name")
	elif isinstance(data, dict) and data.get("name"):
		log_fields["target_reference"] = data["name"]

	insert_log(doc, target, status="Success", **log_fields)
	return data


def get_session() -> requests.Session:
	# Retry connection errors only; a 500 from the target is returned so its error page gets logged
	session = requests.Session()
	session.mount("http://", HTTPAdapter(max_retries=Retry(total=MAX_RETRIES, raise_on_status=False)))
	session.mount("https://", HTTPAdapter(max_retries=Retry(total=MAX_RETRIES, raise_on_status=False)))
	return session


def parse_response(response, key: str = "data") -> tuple[dict | list | str | None, str | None]:
	if not response.ok:
		return None, get_http_error(response)

	try:
		data = response.json()[key]
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
		return _("HTTP {0}: the target refused to delete the Employee. {1}").format(
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
			"subject": _("CentHR delete of Employee {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
