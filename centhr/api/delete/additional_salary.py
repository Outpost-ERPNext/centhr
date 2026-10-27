# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import html
import json
import re
from urllib.parse import quote, unquote

import frappe
import requests
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from requests.adapters import HTTPAdapter, Retry

ADDITIONAL_SALARY_ENDPOINT = "/api/resource/" + quote("Additional Salary")
EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000
# Employee, component, amount and payroll date (from date when recurring) find the record on the target
KEY_FIELDS = ("employee", "salary_component", "amount", "is_recurring", "payroll_date", "from_date")


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_additional_salary_delete(doc, method=None):
	if not get_targets(doc.company):
		return

	frappe.enqueue(
		"centhr.api.delete.additional_salary.delete_additional_salary",
		queue="short",
		job_id=f"centhr_additional_salary_delete::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		additional_salary={
			"name": doc.name,
			"employee": doc.employee,
			"employee_name": doc.employee_name,
			"salary_component": doc.salary_component,
			"amount": doc.amount,
			"is_recurring": doc.is_recurring,
			"payroll_date": str(doc.payroll_date) if doc.payroll_date else None,
			"from_date": str(doc.from_date) if doc.from_date else None,
			"company": doc.company,
			"docstatus": doc.docstatus,
		},
	)


def delete_additional_salary(additional_salary: dict) -> None:
	doc = frappe._dict(additional_salary)
	failed_targets = []

	for target in get_targets(doc.company):
		try:
			sync_to_target(doc, target)
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


def sync_to_target(doc, target) -> None:
	base_url = target.base_url.rstrip("/")
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	url = base_url + ADDITIONAL_SALARY_ENDPOINT
	key = {**doc, "employee": get_target_employee(doc, target, base_url, headers)}
	target_additional_salary = find_target_additional_salary(
		doc, target, url, headers, key, get_target_docstatus(doc)
	)
	if not target_additional_salary:
		insert_log(
			doc,
			target,
			status="Success",
			error=_(
				"No matching Additional Salary of {0} for Employee {1} on {2} in the target system"
			).format(doc.salary_component, doc.employee, doc.payroll_date or doc.from_date),
		)
		return

	target_url = f"{url}/{quote(target_additional_salary['name'], safe='')}"
	if target_additional_salary["docstatus"] == 1:
		# The local cancel did not reach the target; a submitted record cannot be deleted
		send_request(doc, target, "PUT", target_url, headers, json={"docstatus": 2})

	send_request(doc, target, "DELETE", target_url, headers)


def get_target_docstatus(doc) -> list[int]:
	if doc.docstatus == 0:
		return [0]
	# A submitted record on the target with the same key belongs to the local amendment, if there is one
	if has_local_amendment(doc):
		return [2]
	return [1, 2]


def has_local_amendment(doc) -> bool:
	filters = {fieldname: value for fieldname, operator, value in get_key_filters(doc)}
	return bool(
		frappe.db.exists("Additional Salary", {**filters, "docstatus": ("!=", 2), "name": ("!=", doc.name)})
	)


def get_target_employee(doc, target, base_url: str, headers: dict) -> str:
	employee_number = frappe.db.get_value("Employee", doc.employee, "employee_number") or doc.employee
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
	frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Delete Failed"))


def find_target_additional_salary(
	doc, target, url: str, headers: dict, key: dict, docstatus: list[int]
) -> dict | None:
	# key holds the target employee; a submitted record comes before a cancelled one
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps([*get_key_filters(key), ["docstatus", "in", docstatus]]),
			"fields": json.dumps(["name", "docstatus"]),
			"order_by": "docstatus asc",
			"limit_page_length": 1,
		},
	)
	return data[0] if data else None


def get_key_filters(key: dict) -> list:
	date_field = "from_date" if key["is_recurring"] else "payroll_date"
	fieldnames = ("employee", "salary_component", "amount", date_field)
	return [[fieldname, "=", key[fieldname]] for fieldname in fieldnames]


def send_request(doc, target, method: str, url: str, headers: dict, **kwargs) -> dict | list:
	log_fields = {"request_method": method, "endpoint": url, "request_payload": kwargs.get("json")}
	response = None

	try:
		response = get_session().request(method, url, headers=headers, timeout=REQUEST_TIMEOUT, **kwargs)
		data, error = parse_response(response, method)
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
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Delete Failed"))

	if method == "DELETE":
		log_fields["target_reference"] = unquote(url.rsplit("/", 1)[-1])
	elif isinstance(data, dict):
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


def parse_response(response, method: str) -> tuple[dict | list | None, str | None]:
	if not response.ok:
		return None, get_http_error(response)

	if method == "DELETE":
		# older Frappe versions reply with {"message": "ok"} instead of {"data": ...}
		return None, None

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
		return _("HTTP {0}: the target refused to delete the Additional Salary. {1}").format(
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
			"doctypes": "Additional Salary",
			"reference_name": doc.name,
			"name1": doc.get("employee_name") or doc.name,
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
			"subject": _("CentHR delete of Additional Salary {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
