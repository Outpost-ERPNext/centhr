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

PAYROLL_ENTRY_ENDPOINT = "/api/resource/" + quote("Payroll Entry")
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000
# One payroll run of a company per period and posting date, so these find it on the target
KEY_FIELDS = ("company", "payroll_frequency", "start_date", "end_date", "posting_date")


class CentHRSyncError(frappe.ValidationError):
	pass


def enqueue_payroll_entry_delete(doc, method=None):
	if not get_targets(doc.company):
		return

	frappe.enqueue(
		"centhr.api.delete.payroll_entry.delete_payroll_entry",
		queue="short",
		job_id=f"centhr_payroll_entry_delete::{doc.name}",
		deduplicate=True,
		enqueue_after_commit=True,
		payroll_entry={
			**frappe.parse_json(frappe.as_json({fieldname: doc.get(fieldname) for fieldname in KEY_FIELDS})),
			"name": doc.name,
			"docstatus": doc.docstatus,
		},
	)


def delete_payroll_entry(payroll_entry: dict) -> None:
	doc = frappe._dict(payroll_entry)
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
	url = target.base_url.rstrip("/") + PAYROLL_ENTRY_ENDPOINT
	headers = {
		"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
		"Accept": "application/json",
	}

	target_payroll_entry = find_target_payroll_entry(doc, target, url, headers, get_target_docstatus(doc))
	if not target_payroll_entry:
		insert_log(
			doc,
			target,
			status="Success",
			error=_("No matching Payroll Entry for {0} from {1} to {2} in the target system").format(
				doc.company, doc.start_date, doc.end_date
			),
		)
		return

	target_url = f"{url}/{quote(target_payroll_entry['name'], safe='')}"
	if target_payroll_entry["docstatus"] == 1:
		# The local cancel did not reach the target; its own cancel removes the Salary Slips first
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
	filters = {fieldname: doc[fieldname] for fieldname in KEY_FIELDS}
	return bool(
		frappe.db.exists("Payroll Entry", {**filters, "docstatus": ("!=", 2), "name": ("!=", doc.name)})
	)


def find_target_payroll_entry(doc, target, url: str, headers: dict, docstatus: list[int]) -> dict | None:
	# A submitted record comes before a cancelled one
	data = send_request(
		doc,
		target,
		"GET",
		url,
		headers,
		params={
			"filters": json.dumps(
				[[fieldname, "=", doc[fieldname]] for fieldname in KEY_FIELDS]
				+ [["docstatus", "in", docstatus]]
			),
			"fields": json.dumps(["name", "docstatus"]),
			"order_by": "docstatus asc",
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
		return _("HTTP {0}: the target refused to delete the Payroll Entry. {1}").format(
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
			"subject": _("CentHR delete of Payroll Entry {0} failed for: {1}").format(
				doc.name, ", ".join(failed_targets)
			),
		},
	)
