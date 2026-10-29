import frappe

# Staff use the /staff portal; on desk, ERPNext is for admins and Frappe HR for HR.
# Hiding an icon is cosmetic; data access is still enforced by role permissions.
APP_ROLES = {
	"erpnext": {"System Manager"},
	"hrms": {"System Manager", "HR Manager", "HR User"},
}


def extend_bootinfo(bootinfo):
	if frappe.session.user == "Administrator":
		return
	roles = set(frappe.get_roles())
	for app in bootinfo.get("app_data") or []:
		allowed = APP_ROLES.get(app.get("app_name"))
		if allowed is not None and not roles & allowed:
			app["on_apps_screen"] = False
