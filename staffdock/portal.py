import frappe
from werkzeug.exceptions import HTTPException
from werkzeug.utils import redirect

PORTAL = "/staff"
# Pages a staff (Website User) account would otherwise land on: site home, desk, Frappe's own login.
DESK_PATHS = ("/", "/desk", "/app", "/login", "/me")


def redirect_staff_to_portal():
	"""before_request: send logged-in staff to the portal instead of desk's "Not Permitted"."""
	path = frappe.request.path.rstrip("/") or "/"
	if frappe.session.user == "Guest" or frappe.request.method != "GET":
		return
	if path not in DESK_PATHS and not path.startswith(("/desk/", "/app/")):
		return
	if frappe.session.data.user_type == "Website User":
		raise HTTPException(response=redirect(PORTAL, 302))
