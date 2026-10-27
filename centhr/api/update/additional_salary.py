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
from frappe.model import no_value_fields, table_fields
from requests.adapters import HTTPAdapter, Retry

ADDITIONAL_SALARY_ENDPOINT = "/api/resource/" + quote("Additional Salary")
SALARY_COMPONENT_ENDPOINT = "/api/resource/" + quote("Salary Component")
EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000
# Local names: amended_from and the record that created this one (Employee Referral, Employee Advance)
EXCLUDED_FIELDS = ("amended_from", "ref_doctype", "ref_docname")
# Employee, component, amount and payroll date (from date when recurring) find the record on the target
KEY_FIELDS = ("employee", "salary_component", "amount", "is_recurring", "payroll_date", "from_date")
DOCSTATUS_LABELS = {0: "Draft", 1: "Submitted", 2: "Cancelled"}


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_additional_salary_update(doc, method=None):
	# on_update also runs on insert, which post/additional_salary.py handles
	if frappe.flags.centhr_migration or doc.flags.in_insert or not get_targets(doc.company):
		return

	# A draft can change its key fields, so the target record is found by the values before the save
	frappe.enqueue(
		"centhr.api.update.additional_salary.update_additional_salary",
		queue="short",
		job_id=f"centhr_additional_salary_update::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		additional_salary=doc.name,
		key=get_key(doc.get_doc_before_save() or doc),
	)


def update_additional_salary(additional_salary: str, key: dict | None = None) -> None:
	doc = frappe.get_doc("Additional Salary", additional_salary)
	payload = build_payload(doc)
	key = key or get_key(doc)
	failed_targets = []

	for target in get_targets(doc.company):
		try:
			sync_to_target(doc, payload, target, key)
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


def get_key(doc) -> dict:
	return frappe.parse_json(frappe.as_json({fieldname: doc.get(fieldname) for fieldname in KEY_FIELDS}))


def build_payload(doc) -> dict:
	payload = get_field_values(doc)
	for fieldname in EXCLUDED_FIELDS:
		payload.pop(fieldname, None)

	payload["docstatus"] = doc.docstatus
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


def sync_to_target(doc, payload: dict, target, key: dict) -> None:
	base_url = target.base_url.rstrip("/")
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	payload = {**payload, "employee": get_target_employee(doc, target, base_url, headers, doc.employee)}
	if key["employee"] != doc.employee:
		key = {**key, "employee": get_target_employee(doc, target, base_url, headers, key["employee"])}
	else:
		key = {**key, "employee": payload["employee"]}
	url = base_url + ADDITIONAL_SALARY_ENDPOINT

	target_additional_salary = find_target_additional_salary(doc, target, url, headers, key)
	if not target_additional_salary:
		if doc.docstatus == 2:
			insert_log(
				doc,
				target,
				status="Success",
				error=_(
					"Additional Salary {0} is not in the target system, so there is nothing to cancel"
				).format(doc.name),
			)
			return

		# The create never reached the target, so send it now
		validate_target_salary_component(doc, target, base_url, headers, payload["salary_component"])
		send_request(doc, target, "POST", url, headers, json=payload)
		return

	changes = get_changes(doc, payload, target_additional_salary["docstatus"])
	if not changes:
		insert_log(
			doc,
			target,
			status="Success",
			error=_("Nothing to update: Additional Salary {0} is {1} in the target system").format(
				target_additional_salary["name"], DOCSTATUS_LABELS[target_additional_salary["docstatus"]]
			),
		)
		return

	if changes is payload:
		validate_target_salary_component(doc, target, base_url, headers, payload["salary_component"])
	target_url = f"{url}/{quote(target_additional_salary['name'], safe='')}"
	send_request(doc, target, "PUT", target_url, headers, json=changes)


def get_changes(doc, payload: dict, target_docstatus: int) -> dict | None:
	if target_docstatus == 0 and doc.docstatus != 2:
		# A PUT with docstatus 1 submits the draft on the target
		return payload
	if target_docstatus == 1 and doc.docstatus == 2:
		return {"docstatus": 2}
	if target_docstatus == 1 and doc.docstatus == 1:
		# A submitted record only accepts changes to "Allow on Submit" fields
		allowed = [df.fieldname for df in doc.meta.fields if df.allow_on_submit and df.fieldname in payload]
		return {fieldname: payload[fieldname] for fieldname in allowed} or None
	return None


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


def find_target_additional_salary(doc, target, url: str, headers: dict, key: dict) -> dict | None:
	# key holds the target employee
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps([*get_key_filters(key), ["docstatus", "!=", 2]]),
			"fields": json.dumps(["name", "docstatus"]),
			"limit_page_length": 1,
		},
	)
	return data[0] if data else None


def get_key_filters(key: dict) -> list:
	date_field = "from_date" if key["is_recurring"] else "payroll_date"
	fieldnames = ("employee", "salary_component", "amount", date_field)
	return [[fieldname, "=", key[fieldname]] for fieldname in fieldnames]


def validate_target_salary_component(
	doc, target, base_url: str, headers: dict, salary_component: str
) -> None:
	data = send_request(
		doc,
		target,
		"GET",
		base_url + SALARY_COMPONENT_ENDPOINT,
		headers,
		params={
			"filters": json.dumps([["name", "=", salary_component]]),
			"fields": json.dumps(["name"]),
			"limit_page_length": 1,
		},
	)
	if data:
		return

	error = _("Salary Component {0} does not exist in the target system. Sync it first").format(
		salary_component
	)
	insert_log(doc, target, status="Failed", error=error)
	frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Update Failed"))


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


def parse_response(response, method: str) -> tuple[dict | list | None, str | None]:
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
		return _("HTTP {0}: the target rejected the Additional Salary data. {1}").format(
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
			"document_type": "Additional Salary",
			"document_name": doc.name,
			"subject": _("CentHR update of Additional Salary {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
