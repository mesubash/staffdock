"""StaffDock configuration on top of ERPNext. Runs on every `bench migrate`; safe to re-run."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import add_permission, update_permission_property

from staffdock.staffdock.doctype.staffdock_settings import staffdock_settings

RETURN_CONDITIONS = "\nGood\nMinor Wear\nDamaged\nNeeds Repair\nLost\nRetired"

# Staff roles without desk access: these users only ever see the /staff portal.
EMPLOYEE = "Employee"
INVENTORY = "Inventory"


def after_migrate():
	setup_roles()
	setup_custom_fields()
	setup_permissions()
	setup_inventory_request_workflow()
	setup_asset_movement_workflow()
	setup_notifications()
	staffdock_settings.sync_branding()
	lift_own_record_restriction_for_hr()
	# Desk is only for HR/admins; they land on the apps grid (staff never reach desk)
	frappe.db.set_single_value("System Settings", "default_app", "")
	frappe.db.set_single_value("Website Settings", "disable_signup", 1)
	frappe.db.set_single_value("Website Settings", "home_page", "staff")
	frappe.db.commit()


def lift_own_record_restriction_for_hr():
	"""HR/admin staff manage other employees; see events.employee_validate."""
	from staffdock.events import HR_ROLES

	hr_users = set(frappe.get_all("Has Role", filters={"role": ["in", list(HR_ROLES)], "parenttype": "User"}, pluck="parent"))
	for employee in frappe.get_all(
		"Employee", filters={"create_user_permission": 1, "user_id": ["in", list(hr_users) or [""]]}, pluck="name"
	):
		frappe.get_doc("Employee", employee).save(ignore_permissions=True)


def setup_roles():
	_ensure("Role", INVENTORY, role_name=INVENTORY, desk_access=0)
	# ERPNext gives every linked user "Employee"; without desk access they are Website Users
	# and can only use the portal. HR/Admin keep desk through their own roles.
	frappe.db.set_value("Role", EMPLOYEE, {"desk_access": 0, "home_page": "staff"})
	frappe.db.set_value("Role", "Desk User", "home_page", "")
	# HRMS gives approvers these roles automatically; approvals happen in the portal, not desk
	for role in ("Leave Approver", "Expense Approver"):
		if frappe.db.get_value("Role", role, "desk_access"):
			frappe.db.set_value("Role", role, "desk_access", 0)
			# user_type is worked out from roles on save; recompute for current holders
			for user in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent"):
				frappe.get_doc("User", user).save(ignore_permissions=True)


def setup_custom_fields():
	create_custom_fields(
		{
			"Material Request": [
				{
					"fieldname": "sd_employee",
					"label": "Requested By (Employee)",
					"fieldtype": "Link",
					"options": "Employee",
					"read_only": 1,
					# row access is enforced in staffdock.permissions, not by Employee user permissions
					"ignore_user_permissions": 1,
					"insert_after": "material_request_type",
				},
				{
					"fieldname": "sd_employee_name",
					"label": "Employee Name",
					"fieldtype": "Data",
					"fetch_from": "sd_employee.employee_name",
					"read_only": 1,
					"insert_after": "sd_employee",
				},
				{
					"fieldname": "sd_approver",
					"label": "Reporting Manager",
					"fieldtype": "Link",
					"options": "User",
					"read_only": 1,
					"insert_after": "sd_employee_name",
				},
				{
					"fieldname": "sd_approver_name",
					"label": "Reporting Manager Name",
					"fieldtype": "Data",
					"read_only": 1,
					"insert_after": "sd_approver",
				},
				{
					"fieldname": "sd_reason",
					"label": "Reason",
					"fieldtype": "Small Text",
					"insert_after": "sd_approver_name",
				},
			],
			"Asset Movement": [
				{
					"fieldname": "sd_return_condition",
					"label": "Return Condition",
					"fieldtype": "Select",
					"options": RETURN_CONDITIONS,
					"depends_on": "eval:doc.purpose=='Receipt'",
					"mandatory_depends_on": "eval:doc.purpose=='Receipt'",
					"insert_after": "purpose",
				},
			],
		},
		update=True,
	)
	make_property_setter("Material Request", "material_request_type", "default", "Material Issue", "Text")
	# Short, readable request numbers: REQ-00001
	make_property_setter("Material Request", "naming_series", "options", "REQ-.#####", "Text")
	make_property_setter("Material Request", "naming_series", "default", "REQ-.#####", "Text")
	make_property_setter("Asset", "naming_series", "options", "AST-.#####", "Text")
	make_property_setter("Asset", "naming_series", "default", "AST-.#####", "Text")
	# Keep a version per save so the portal can show who moved a request/asset and when
	for doctype in ("Material Request", "Asset Movement"):
		make_property_setter(doctype, None, "track_changes", 1, "Check", for_doctype=True)


def _grant(doctype, role, *ptypes):
	if not frappe.db.exists("Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}):
		add_permission(doctype, role, 0)
	for ptype in ptypes:
		update_permission_property(doctype, role, 0, ptype, 1, validate=False)


def setup_permissions():
	# Employees: row-level filtered in staffdock.permissions.
	# "submit" is required by Frappe to move a submitted doc between workflow states
	# (acknowledge receipt); the workflow still decides which transitions are allowed.
	_grant("Material Request", "Employee", "read", "write", "create", "submit")
	_grant("Asset", "Employee", "read")
	_grant("Asset Movement", "Employee", "read", "write", "submit")
	# Check-ins only through staffdock.api.check_in_out (server time); employees can still read their own
	for ptype in ("create", "write", "delete"):
		update_permission_property("Employee Checkin", EMPLOYEE, 0, ptype, 0, validate=False)
	# Needed to pick items in a request
	for doctype in ("Item", "Warehouse", "UOM"):
		_grant(doctype, "Employee", "read")

	# Inventory staff run stores and the asset register from the portal
	for doctype in ("Material Request", "Stock Entry", "Asset", "Asset Movement"):
		_grant(doctype, INVENTORY, "read", "write", "create", "submit")
	_grant("Item", INVENTORY, "read", "write", "create")
	for doctype in ("Warehouse", "UOM", "Bin", "Location", "Company", "Stock Entry Type"):
		_grant(doctype, INVENTORY, "read")


def _ensure(doctype, name, **values):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert(ignore_permissions=True)


def _workflow(name, document_type, states, transitions):
	for state, style in {s[0]: s[3] for s in states}.items():
		_ensure("Workflow State", state, workflow_state_name=state, style=style)
	for action in {t[1] for t in transitions}:
		_ensure("Workflow Action Master", action, workflow_action_name=action)

	wf = frappe.get_doc("Workflow", name) if frappe.db.exists("Workflow", name) else frappe.new_doc("Workflow")
	wf.update(
		{
			"workflow_name": name,
			"document_type": document_type,
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"override_status": 0,
		}
	)
	wf.set("states", [{"state": s, "doc_status": str(d), "allow_edit": r} for s, d, r, _ in states])
	wf.set(
		"transitions",
		[
			{
				"state": a,
				"action": act,
				"next_state": b,
				"allowed": role,
				"condition": cond,
				"allow_self_approval": self_ok,
			}
			for a, act, b, role, cond, self_ok in transitions
		],
	)
	wf.save(ignore_permissions=True)


OWNER = "doc.owner == frappe.session.user"


def setup_inventory_request_workflow():
	# (state, docstatus, role allowed to edit, style)
	states = [
		("Draft", 0, "Employee", ""),
		("Pending Manager Approval", 0, INVENTORY, "Warning"),
		("Manager Rejected", 0, "Employee", "Danger"),
		("Pending Inventory Review", 0, INVENTORY, "Warning"),
		("Inventory Rejected", 0, INVENTORY, "Danger"),
		("Approved", 1, INVENTORY, "Primary"),
		("Completed", 1, INVENTORY, "Success"),
		("Closed", 1, INVENTORY, ""),
	]
	approver = "doc.sd_approver == frappe.session.user"
	# (from, action, to, role, condition, allow_self_approval)
	transitions = [
		("Draft", "Submit", "Pending Manager Approval", "Employee", f"{OWNER} and doc.sd_approver", 1),
		("Draft", "Submit", "Pending Inventory Review", "Employee", f"{OWNER} and not doc.sd_approver", 1),
		("Pending Manager Approval", "Approve", "Pending Inventory Review", "Employee", approver, 0),
		("Pending Manager Approval", "Reject", "Manager Rejected", "Employee", approver, 0),
		("Pending Inventory Review", "Approve", "Approved", INVENTORY, None, 0),
		("Pending Inventory Review", "Reject", "Inventory Rejected", INVENTORY, None, 0),
		("Approved", "Acknowledge Receipt", "Completed", "Employee", f"{OWNER} and doc.status == 'Issued'", 1),
		# Approved but can't (or won't) be fulfilled, e.g. out of stock: inventory closes it
		("Approved", "Close", "Closed", INVENTORY, "doc.status != 'Issued'", 0),
	]
	_workflow("Inventory Request", "Material Request", states, transitions)


def setup_asset_movement_workflow():
	states = [
		("Draft", 0, INVENTORY, ""),
		("Pending Acknowledgement", 1, INVENTORY, "Warning"),
		("Acknowledged", 1, INVENTORY, "Success"),
		("Completed", 1, INVENTORY, "Success"),
	]
	receiver = (
		"frappe.db.get_value('Employee', doc.assets[0].to_employee, 'user_id') == frappe.session.user"
	)
	transitions = [
		("Draft", "Issue", "Pending Acknowledgement", INVENTORY, "doc.purpose == 'Issue'", 1),
		("Draft", "Submit", "Completed", INVENTORY, "doc.purpose != 'Issue'", 1),
		("Pending Acknowledgement", "Acknowledge Receipt", "Acknowledged", "Employee", receiver, 1),
	]
	_workflow("Asset Handover", "Asset Movement", states, transitions)


def setup_notifications():
	mr = "Material Request"
	# (name, field watched, condition, recipient kwargs, subject shown in the portal's updates)
	notifications = [
		(
			"Request Awaiting Manager",
			"workflow_state",
			"doc.workflow_state == 'Pending Manager Approval'",
			{"receiver_by_document_field": "sd_approver"},
			"{{ doc.sd_employee_name }} needs your approval for {{ doc.name }}",
		),
		(
			"Request Awaiting Inventory",
			"workflow_state",
			"doc.workflow_state == 'Pending Inventory Review'",
			{"receiver_by_role": INVENTORY},
			"{{ doc.name }} from {{ doc.sd_employee_name }} is ready for review",
		),
		(
			"Request Decision",
			"workflow_state",
			"doc.workflow_state in ('Manager Rejected', 'Inventory Rejected', 'Approved', 'Closed')",
			{"receiver_by_document_field": "owner"},
			"Your request {{ doc.name }} was {{ 'rejected' if 'Rejected' in doc.workflow_state else doc.workflow_state | lower }}",
		),
		(
			"Request Issued",
			"status",
			"doc.status == 'Issued'",
			{"receiver_by_document_field": "owner"},
			"Items for {{ doc.name }} were issued. Please confirm you received them",
		),
	]
	notifications = [(name, mr, "Value Change", *rest) for name, *rest in notifications] + [
		(
			"Leave Awaiting Approval",
			"Leave Application",
			"New",
			None,
			"doc.leave_approver",
			{"receiver_by_document_field": "leave_approver"},
			"{{ doc.employee_name }} applied for {{ doc.leave_type }} from {{ doc.from_date }}",
		),
		(
			"Leave Decision",
			"Leave Application",
			"Value Change",
			"status",
			"doc.status in ('Approved', 'Rejected')",
			{"receiver_by_document_field": "owner"},
			"Your {{ doc.leave_type }} from {{ doc.from_date }} was {{ doc.status | lower }}",
		),
	]
	for name, doctype, event, field, condition, recipient, subject in notifications:
		n = frappe.get_doc("Notification", name) if frappe.db.exists("Notification", name) else frappe.new_doc("Notification")
		n.update(
			{
				"name": name,
				"__newname": name,
				"enabled": 1,
				"channel": "System Notification",
				"document_type": doctype,
				"event": event,
				"value_changed": field,
				"condition": condition,
				"subject": subject,
				"message": subject,
			}
		)
		n.set("recipients", [recipient])
		n.save(ignore_permissions=True)
