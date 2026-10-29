import frappe
from frappe.model.document import Document


class StaffDockSettings(Document):
	def validate(self):
		self.email_domain = (self.email_domain or "").strip().lower().lstrip("@")

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.doctype)


def get():
	"""Branding and policy used across the app and portal."""
	s = frappe.get_cached_doc("StaffDock Settings")
	return frappe._dict(
		app_title=s.app_title or "StaffDock",
		logo=s.logo or "/assets/staffdock/images/logo.svg",
		email_domain=s.email_domain or "",
		default_warehouse=s.default_warehouse,
	)
