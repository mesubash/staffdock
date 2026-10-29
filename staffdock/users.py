"""Staff accounts: only the company email domain (StaffDock Settings), when one is set."""

import frappe
from frappe import _

from staffdock.staffdock.doctype.staffdock_settings import staffdock_settings

SYSTEM_USERS = {"Administrator", "Guest"}


def user_validate(doc, method=None):
	domain = staffdock_settings.get().email_domain
	if not domain or doc.name in SYSTEM_USERS:
		return
	if (doc.email or "").lower().rpartition("@")[2] != domain:
		frappe.throw(_("Only @{0} accounts are allowed.").format(domain))
