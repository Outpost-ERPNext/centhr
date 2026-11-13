# Copyright (c) 2026, Outpost Work LLP and contributors
# For license information, please see license.txt

"""Data for the Architecture page: the entity sites CentHR syncs with.

Each row in CentHr Settings > Authorization connects one company to one site. Only the company
and the site host are returned, never the API key or secret.
"""

from urllib.parse import urlparse

import frappe


@frappe.whitelist()
def get_connected_sites():
	settings = frappe.get_cached_doc("CentHr Settings")
	show_host = frappe.has_permission("CentHr Settings", "read")
	sites = {}

	for row in settings.get("authorization") or []:
		if not row.company or row.company in sites:
			continue
		sites[row.company] = {
			"company": row.company,
			"host": host_of(row.base_url) if show_host else None,
		}

	return list(sites.values())


def host_of(url):
	if not url:
		return None
	return urlparse(url if "://" in url else f"https://{url}").hostname
