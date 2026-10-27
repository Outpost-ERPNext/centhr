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

PAYROLL_ENTRY_ENDPOINT = "/api/resource/" + quote("Payroll Entry")
EMPLOYEE_ENDPOINT = "/api/resource/Employee"
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000
# Local names, employee filters (the employees table is sent instead) and the status fields the target sets
EXCLUDED_FIELDS = (
	"amended_from",
	"branch",
	"department",
	"designation",
	"grade",
	"project",
	"bank_account",
	"status",
	"salary_slips_created",
	"salary_slips_submitted",
	"error_message",
)
# Fetched from the employee by the target
EXCLUDED_EMPLOYEE_FIELDS = ("department", "designation")
# One payroll run of a company per period and posting date, so these find it on the target
KEY_FIELDS = ("company", "payroll_frequency", "start_date", "end_date", "posting_date")


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_payroll_entry_sync(doc, method=None):
	# Records migrated from the CentHR site must not be sent back to it
	if frappe.flags.centhr_migration or not get_targets(doc.company):
		return

	frappe.enqueue(
		"centhr.api.post.payroll_entry.sync_payroll_entry",
		queue="short",
		job_id=f"centhr_payroll_entry_sync::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		payroll_entry=doc.name,
	)


def sync_payroll_entry(payroll_entry: str) -> None:
	doc = frappe.get_doc("Payroll Entry", payroll_entry)
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
	for fieldname in EXCLUDED_FIELDS:
		payload.pop(fieldname, None)
	for row in payload["employees"]:
		for fieldname in EXCLUDED_EMPLOYEE_FIELDS:
			row.pop(fieldname, None)

	# Submitting on the target creates draft Salary Slips there; they are never submitted from here
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


def sync_to_target(doc, payload: dict, target) -> None:
	base_url = target.base_url.rstrip("/")
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	url = base_url + PAYROLL_ENTRY_ENDPOINT
	if find_target_payroll_entry(doc, target, url, headers, payload):
		insert_log(
			doc,
			target,
			status="Success",
			error=_("Payroll Entry for {0} from {1} to {2} already exists in the target system").format(
				doc.company, payload["start_date"], payload["end_date"]
			),
		)
		return

	payload = {**payload, "employees": get_target_employee_rows(doc, target, base_url, headers, payload)}
	send_request(doc, target, "POST", url, headers, json=payload)


def get_target_employee_rows(doc, target, base_url: str, headers: dict, payload: dict) -> list[dict]:
	employees = [row["employee"] for row in payload["employees"]]
	if not employees:
		return []

	employee_numbers = {
		name: employee_number or name
		for name, employee_number in frappe.get_all(
			"Employee", filters={"name": ("in", employees)}, fields=["name", "employee_number"], as_list=True
		)
	}
	data = send_request(
		doc,
		target,
		"GET",
		base_url + EMPLOYEE_ENDPOINT,
		headers,
		params={
			"filters": json.dumps([["employee_number", "in", sorted(set(employee_numbers.values()))]]),
			"fields": json.dumps(["name", "employee_number"]),
			"limit_page_length": 0,
		},
	)
	target_employees = {row["employee_number"]: row["name"] for row in data}

	missing = [
		employee_numbers.get(e, e) for e in employees if employee_numbers.get(e, e) not in target_employees
	]
	if missing:
		error = _("Employee {0} is not synced to the target system").format(", ".join(missing))
		insert_log(doc, target, status="Failed", error=error)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Sync Failed"))

	return [
		{**row, "employee": target_employees[employee_numbers.get(row["employee"], row["employee"])]}
		for row in payload["employees"]
	]


def find_target_payroll_entry(doc, target, url: str, headers: dict, key: dict) -> dict | None:
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps(
				[[fieldname, "=", key[fieldname]] for fieldname in KEY_FIELDS] + [["docstatus", "!=", 2]]
			),
			"fields": json.dumps(["name", "docstatus"]),
			"limit_page_length": 1,
		},
	)
	return data[0] if data else None


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

	if method == "POST" and response is not None and response.status_code == 409:
		insert_log(
			doc,
			target,
			status="Success",
			error=_("Payroll Entry already exists in the target system"),
			**log_fields,
		)
		return {}

	if error:
		insert_log(doc, target, status="Failed", error=error, **log_fields)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Sync Failed"))

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
		return _("HTTP {0}: the target rejected the Payroll Entry data. {1}").format(
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
			"doctypes": "Payroll Entry",
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
			"document_type": "Payroll Entry",
			"document_name": doc.name,
			"subject": _("CentHR sync of Payroll Entry {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
