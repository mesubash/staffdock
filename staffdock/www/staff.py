import os

import frappe

from staffdock.staffdock.doctype.staffdock_settings import staffdock_settings

no_cache = 1


def get_context(context):
	# The portal is a single-page app; Frappe hands it the CSRF token, branding and the built bundle.
	bundle = frappe.get_app_path("staffdock", "public", "portal", "portal.js")
	settings = staffdock_settings.get()
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.version = int(os.path.getmtime(bundle)) if os.path.exists(bundle) else 0
	context.title = settings.app_title
	context.logo = settings.logo
	context.boot = frappe.as_json(
		{"title": settings.app_title, "logo": settings.logo, "email_domain": settings.email_domain}
	)
