import frappe
from frappe.model.document import Document

DEFAULT_LOGO = "/assets/staffdock/images/logo.svg"


class StaffDockSettings(Document):
	def validate(self):
		self.email_domain = (self.email_domain or "").strip().lower().lstrip("@")

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.doctype)
		sync_branding()


def get():
	"""Branding and policy used across the app and portal."""
	s = frappe.get_cached_doc("StaffDock Settings")
	return frappe._dict(
		app_title=s.app_title or "StaffDock",
		logo=s.logo or DEFAULT_LOGO,
		email_domain=s.email_domain or "",
		default_warehouse=s.default_warehouse,
	)


def sync_branding():
	"""Frappe's own login page reads name and logo from Website Settings."""
	s = get()
	frappe.db.set_single_value("Website Settings", {"app_name": s.app_title, "app_logo": s.logo})
	frappe.clear_cache()
