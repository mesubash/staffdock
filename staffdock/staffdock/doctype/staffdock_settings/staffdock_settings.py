import frappe
from frappe import _
from frappe.model.document import Document

DEFAULT_LOGO = "/assets/staffdock/images/logo.svg"


class StaffDockSettings(Document):
	def validate(self):
		self.email_domain = (self.email_domain or "").strip().lower().lstrip("@")
		if self.send_email_notifications and not frappe.db.exists(
			"Email Account", {"enable_outgoing": 1, "default_outgoing": 1}
		):
			frappe.msgprint(
				_("Emails will wait in the queue until you add a default outgoing Email Account."),
				title=_("No outgoing email account"),
				indicator="orange",
			)

	def on_update(self):
		frappe.clear_document_cache(self.doctype, self.doctype)
		sync_branding()
		if self.has_value_changed("send_email_notifications"):
			from staffdock.setup import setup_notifications

			setup_notifications()


def get():
	"""Branding and policy used across the app and portal."""
	s = frappe.get_cached_doc("StaffDock Settings")
	return frappe._dict(
		app_title=s.app_title or "StaffDock",
		logo=s.logo or DEFAULT_LOGO,
		email_domain=s.email_domain or "",
		default_warehouse=s.default_warehouse,
		send_email_notifications=bool(s.send_email_notifications),
	)


def sync_branding():
	"""Frappe's own login page reads name and logo from Website Settings."""
	s = get()
	frappe.db.set_single_value("Website Settings", {"app_name": s.app_title, "app_logo": s.logo})
	frappe.clear_cache()
