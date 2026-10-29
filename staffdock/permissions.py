"""Row-level access for plain employees.

Users with any STAFF_ROLES see everything their role permissions allow.
Everyone else (role "Employee") sees only:
- Material Request: ones they created, or ones waiting on them as reporting manager
- Asset: assets in their custody
- Asset Movement: movements to or from them
"""

import frappe

STAFF_ROLES = {"System Manager", "Inventory", "Stock Manager", "Stock User", "Accounts User", "Accounts Manager"}


def _is_staff(user):
	return user == "Administrator" or bool(STAFF_ROLES & set(frappe.get_roles(user)))


def _employee(user):
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def material_request_query(user=None):
	user = user or frappe.session.user
	if _is_staff(user):
		return ""
	u = frappe.db.escape(user)
	return f"(`tabMaterial Request`.owner = {u} or `tabMaterial Request`.sd_approver = {u})"


def material_request_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if _is_staff(user) or doc.is_new():
		return True
	return user in (doc.owner, doc.sd_approver)


def asset_query(user=None):
	user = user or frappe.session.user
	if _is_staff(user):
		return ""
	return f"`tabAsset`.custodian = {frappe.db.escape(_employee(user) or '')}"


def asset_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if _is_staff(user):
		return True
	employee = _employee(user)
	return bool(employee) and doc.custodian == employee


def asset_movement_query(user=None):
	user = user or frappe.session.user
	if _is_staff(user):
		return ""
	e = frappe.db.escape(_employee(user) or "")
	return (
		"exists (select 1 from `tabAsset Movement Item` i where i.parent = `tabAsset Movement`.name"
		f" and (i.to_employee = {e} or i.from_employee = {e}))"
	)


def asset_movement_has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if _is_staff(user):
		return True
	employee = _employee(user)
	return bool(employee) and any(employee in (row.to_employee, row.from_employee) for row in doc.assets)
