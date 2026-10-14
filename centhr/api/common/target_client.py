# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

import json
from urllib.parse import quote

import frappe
import requests
from frappe import _
from frappe.utils import get_request_session

from centhr.api.post.employee import (
	MAX_RETRIES,
	REQUEST_TIMEOUT,
	RESPONSE_LOG_LIMIT,
	CentHRSyncError,
	get_target_message,
)


class TargetClient:
	"""REST client for one CentHr Settings target. Logs every request against `ref`."""

	def __init__(self, target, ref):
		self.target = target
		self.ref = ref

	def get_list(
		self, doctype: str, filters: list, fields: list, or_filters: list | None = None, limit: int = 1
	) -> list:
		params = {"filters": json.dumps(filters), "fields": json.dumps(fields), "limit_page_length": limit}
		if or_filters:
			params["or_filters"] = json.dumps(or_filters)
		return self.request("GET", self.url(doctype), params=params)

	def insert(self, doctype: str, payload: dict) -> dict:
		return self.request("POST", self.url(doctype), json=payload)

	def update(self, doctype: str, name: str, payload: dict) -> dict:
		return self.request("PUT", self.url(doctype, name), json=payload)

	def delete(self, doctype: str, name: str) -> None:
		self.request("DELETE", self.url(doctype, name))

	def fail(self, error: str, **log_fields):
		self.log("Failed", error=error, **log_fields)
		frappe.throw(error, exc=CentHRSyncError, title=_("CentHR Sync Failed"))

	def url(self, doctype: str, name: str | None = None) -> str:
		url = f"{self.target.base_url.rstrip('/')}/api/resource/{quote(doctype)}"
		return f"{url}/{quote(name, safe='')}" if name else url

	def request(self, method: str, url: str, **kwargs) -> dict | list | None:
		log_fields = {"request_method": method, "endpoint": url, "request_payload": kwargs.get("json")}
		response = None

		try:
			response = get_request_session(MAX_RETRIES).request(
				method, url, headers=self.headers(), timeout=REQUEST_TIMEOUT, **kwargs
			)
			data, error = parse_response(response, method, self.ref.doctype)
		except requests.Timeout:
			data, error = None, _("Request timed out after {0} seconds").format(sum(REQUEST_TIMEOUT))
		except requests.ConnectionError:
			data, error = None, _("Could not connect to the target system")
		except requests.RequestException as e:
			data, error = None, f"{type(e).__name__}: {e}"

		if response is not None:
			log_fields.update(
				http_status=response.status_code, api_response=response.text[:RESPONSE_LOG_LIMIT]
			)

		if method == "DELETE" and response is not None and response.status_code == 404:
			self.log("Success", error=_("Already deleted in the target system"), **log_fields)
			return None

		if error:
			self.fail(error, **log_fields)

		if method in ("POST", "PUT"):
			log_fields["target_reference"] = data.get("name")
		elif method == "GET" and data:
			log_fields["target_reference"] = data[0].get("name")

		self.log("Success", **log_fields)
		return data

	def headers(self) -> dict:
		return {
			"Authorization": f"token {self.target.api_key}:{self.target.get_password('api_secret')}",
			"Accept": "application/json",
		}

	def log(self, status: str, error: str | None = None, **fields) -> None:
		if isinstance(fields.get("request_payload"), dict):
			fields["request_payload"] = frappe.as_json(fields["request_payload"])

		frappe.get_doc(
			{
				"doctype": "CentHR API Logger",
				"doctypes": self.ref.doctype,
				"reference_name": self.ref.name,
				"name1": self.ref.label,
				"company": self.target.company,
				"status": status,
				"error": error,
				**fields,
			}
		).insert(ignore_permissions=True)


def parse_response(response, method: str, doctype: str) -> tuple[dict | list | None, str | None]:
	if not response.ok:
		return None, get_http_error(response, doctype)

	if method == "DELETE":
		# older Frappe versions reply with {"message": "ok"} instead of {"data": ...}
		return None, None

	try:
		data = response.json()["data"]
	except ValueError, KeyError, TypeError:
		return None, _("Malformed response from the target system")

	return data, None


def get_http_error(response, doctype: str) -> str:
	status = response.status_code
	if status in (401, 403):
		return _(
			"HTTP {0}: authentication failed or permission denied. Check the API Key and API Secret in CentHr Settings"
		).format(status)
	if status == 404:
		return _("HTTP 404: not found. Check the Base URL in CentHr Settings")
	if status == 409:
		return _("HTTP 409: {0} already exists in the target system").format(doctype)
	if status in (400, 417, 422):
		return _("HTTP {0}: the target rejected the {1} data. {2}").format(
			status, doctype, get_target_message(response)
		)
	if status >= 500:
		return _("HTTP {0}: target server error. {1}").format(status, get_target_message(response))
	return _("HTTP {0}: unexpected response").format(status)
