# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Turn the raw errors written by the sync jobs into messages a user can act on."""

import html
import json
import re
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import strip_html

MISSING_FIELDS_RE = re.compile(r"Missing fields required by the target system: (.+)")
EMPLOYEE_NOT_SYNCED_RE = re.compile(r"Employee (.+?) is not synced to the target system")
PYTHON_ERROR_RE = re.compile(r"^(\w+(?:Error|Exception)): (.+)", re.DOTALL)


def get_readable_error(log) -> str | None:
	error = (log.error or "").strip()
	if not error:
		return None

	server_message = get_server_message(log.api_response)
	for get_message in (get_connection_error, get_http_error, get_sync_error, get_python_error):
		message = get_message(log, error, server_message)
		if message:
			return message

	return clean_text(error)


def get_connection_error(log, error: str, server_message: str | None) -> str | None:
	host = get_host(log.endpoint)
	if "too many 500 error responses" in error:
		return _(
			"The CentHR server at {0} kept failing with a server error, even after retrying. "
			"Check that the CentHR server is working, then resync."
		).format(host)
	if "timed out" in error.lower() or "Timeout" in error:
		return _("The CentHR server at {0} did not reply in time. It may be slow or down. Resync later.").format(
			host
		)
	if any(text in error for text in ("Could not connect", "ConnectionError", "Max retries exceeded")):
		return _(
			"Could not connect to the CentHR server at {0}. "
			"Check that it is running and that the Base URL in CentHr Settings is correct."
		).format(host)


def get_http_error(log, error: str, server_message: str | None) -> str | None:
	status = log.http_status or 0
	if status < 400:
		return None

	host = get_host(log.endpoint)
	if "BrokenPipeError" in error or "BrokenPipeError" in (log.api_response or ""):
		return _(
			"The CentHR server at {0} crashed while it handled the request (broken pipe). "
			"This is a problem on the CentHR server and is usually temporary. Resync to try again."
		).format(host)
	if status in (401, 403):
		return _(
			"CentHR did not accept the API Key and API Secret of company {0}. Check them in CentHr Settings."
		).format(log.company)
	if status == 404:
		if server_message:
			return _("CentHR could not find something it needed: {0}").format(server_message)
		return _("The address {0} does not exist on CentHR. Check the Base URL in CentHr Settings.").format(
			log.endpoint
		)
	if status == 409:
		return _("This {0} already exists on CentHR.").format(log.doctypes)
	if status in (400, 417, 422):
		return _("CentHR rejected the {0}: {1}").format(log.doctypes, server_message or _("no reason given"))
	if status >= 500:
		if server_message:
			return _("The CentHR server had an error: {0}").format(server_message)
		return _("The CentHR server at {0} had an error (HTTP {1}). Check the CentHR server logs.").format(
			host, status
		)
	return _("CentHR sent an unexpected reply (HTTP {0}). {1}").format(status, server_message or "").strip()


def get_sync_error(log, error: str, server_message: str | None) -> str | None:
	if match := MISSING_FIELDS_RE.match(error):
		labels = [get_label(log.doctypes, fieldname.strip()) for fieldname in match[1].split(",")]
		return _(
			"{0} {1} cannot be sent to CentHR because these fields are empty: {2}. "
			"Fill them in and save the {0} again."
		).format(log.doctypes, log.reference_name, ", ".join(labels))
	if match := EMPLOYEE_NOT_SYNCED_RE.match(error):
		return _(
			"Employee {0} does not exist on CentHR yet. Sync the Employee first, then resync this log."
		).format(match[1])


def get_python_error(log, error: str, server_message: str | None) -> str | None:
	if match := PYTHON_ERROR_RE.match(error):
		return clean_text(match[2])


def get_server_message(api_response: str | None) -> str | None:
	try:
		body = json.loads(api_response or "")
	except ValueError:
		return None
	if not isinstance(body, dict):
		return None

	messages = []
	try:
		for raw in json.loads(body.get("_server_messages") or "[]"):
			message = json.loads(raw).get("message") if raw.startswith("{") else raw
			if message:
				messages.append(clean_text(message))
	except (ValueError, TypeError, AttributeError):
		pass
	if messages:
		return " ".join(messages)

	exception = body.get("exception") or ""
	return clean_text(exception.split(": ", 1)[-1]) if exception else None


def get_label(doctype: str, fieldname: str) -> str:
	try:
		return _(frappe.get_meta(doctype).get_label(fieldname))
	except Exception:
		return fieldname


def get_host(endpoint: str | None) -> str:
	return urlparse(endpoint).netloc if endpoint else _("the CentHR server")


def clean_text(text: str) -> str:
	"""Drop HTML and tracebacks, keeping the first meaningful line."""
	lines = [line.strip() for line in html.unescape(strip_html(text)).splitlines()]
	return next((line for line in lines if line), "")
