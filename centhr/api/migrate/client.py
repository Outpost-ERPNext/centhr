# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Read records from a company's connected CentHR site, which is the source of a migration."""

import html
import json
import re
from urllib.parse import quote

import frappe
import requests
from frappe import _
from requests.adapters import HTTPAdapter, Retry

RESOURCE_ENDPOINT = "/api/resource"
PAGE_LENGTH = 500
REQUEST_TIMEOUT = (10, 30)
MAX_RETRIES = 2
RESPONSE_LOG_LIMIT = 10000


class MigrationError(frappe.ValidationError):
	"""A failed request or record. `log_fields` holds the request details for CentHR API Logger."""

	def __init__(self, message: str, log_fields: dict | None = None):
		super().__init__(message)
		self.log_fields = log_fields or {}


class TargetClient:
	def __init__(self, company: str):
		target = get_target(company)
		self.company = company
		self.base_url = target.base_url.rstrip("/")
		self.headers = {
			"Authorization": f"token {target.api_key}:{target.get_password('api_secret')}",
			"Accept": "application/json",
		}
		self.session = get_session()

	def get_all(self, doctype: str, filters: list, fields: list) -> list[dict]:
		"""Read every matching record, one page at a time."""
		records = []
		while True:
			page = self.request(
				"GET",
				self.get_url(doctype),
				params={
					"filters": json.dumps(filters),
					"fields": json.dumps(fields),
					"order_by": "name asc",
					"limit_start": len(records),
					"limit_page_length": PAGE_LENGTH,
				},
			)
			records.extend(page)
			if len(page) < PAGE_LENGTH:
				return records

	def get_doc(self, doctype: str, name: str) -> dict:
		return self.request("GET", self.get_url(doctype, name))

	def get_url(self, doctype: str, name: str | None = None) -> str:
		url = f"{self.base_url}{RESOURCE_ENDPOINT}/{quote(doctype)}"
		return f"{url}/{quote(name, safe='')}" if name else url

	def request(self, method: str, url: str, **kwargs) -> dict | list:
		log_fields = {"request_method": method, "endpoint": url}
		response = None

		try:
			response = self.session.request(
				method, url, headers=self.headers, timeout=REQUEST_TIMEOUT, **kwargs
			)
			data, error = parse_response(response)
		except requests.Timeout:
			data, error = None, _("Request timed out after {0} seconds").format(sum(REQUEST_TIMEOUT))
		except requests.ConnectionError:
			data, error = None, _("Could not connect to the CentHR site")
		except requests.RequestException as e:
			data, error = None, f"{type(e).__name__}: {e}"

		if response is not None:
			log_fields.update(
				http_status=response.status_code, api_response=response.text[:RESPONSE_LOG_LIMIT]
			)

		if error:
			raise MigrationError(error, log_fields)
		return data


def get_target(company: str):
	rows = [row for row in frappe.get_cached_doc("CentHr Settings").authorization if row.company == company]
	if not rows:
		frappe.throw(
			_("Company {0} has no connected CentHR site. Add it in CentHr Settings > Authorization.").format(
				frappe.bold(company)
			),
			title=_("Missing Configuration"),
		)
	return rows[0]


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
		return None, _("Malformed response from the CentHR site")

	return data, None


def get_http_error(response) -> str:
	status = response.status_code
	if status in (401, 403):
		return _(
			"HTTP {0}: authentication failed. Check the API Key and API Secret in CentHr Settings"
		).format(status)
	if status == 404:
		return _("HTTP 404: not found on the CentHR site. Check the Base URL in CentHr Settings")
	if status in (400, 417, 422):
		return _("HTTP {0}: the CentHR site rejected the request. {1}").format(
			status, get_target_message(response)
		)
	if status >= 500:
		return _("HTTP {0}: CentHR server error. {1}").format(status, get_target_message(response))
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
	title = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
	return html.unescape(title.group(1)).strip() if title else text[:500]
