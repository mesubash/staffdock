"""StaffDock configuration on top of ERPNext. Runs on every `bench migrate`; safe to re-run."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.permissions import add_permission, update_permission_property

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
	# Desk is only for HR/admins; they land on the apps grid (staff never reach desk)
	frappe.db.set_single_value("System Settings", "default_app", "")
	frappe.db.set_single_value("Website Settings", "disable_signup", 1)
	frappe.db.set_single_value("Website Settings", "home_page", "staff")
	frappe.db.commit()


def setup_roles():
	_ensure("Role", INVENTORY, role_name=INVENTORY, desk_access=0)
	# ERPNext gives every linked user "Employee"; without desk access they are Website Users
	# and can only use the portal. HR/Admin keep desk through their own roles.
	frappe.db.set_value("Role", EMPLOYEE, {"desk_access": 0, "home_page": "staff"})
	frappe.db.set_value("Role", "Desk User", "home_page", "")


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
					"fieldname": "sd_reason",
					"label": "Reason",
					"fieldtype": "Small Text",
					"insert_after": "sd_approver",
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
	]
	approver = "doc.sd_approver == frappe.session.user"
	# (from, action, to, role, condition, allow_self_approval)
	transitions = [
		("Draft", "Submit", "Pending Manager Approval", "Employee", f"{OWNER} and doc.sd_approver", 1),
		("Draft", "Submit", "Pending Inventory Review", "Employee", f"{OWNER} and not doc.sd_approver", 1),
		("Pending Manager Approval", "Approve", "Pending Inventory Review", "Employee", approver, 0),
		("Pending Manager Approval", "Reject", "Manager Rejected", "Employee", approver, 0),
		("Manager Rejected", "Revise", "Draft", "Employee", OWNER, 1),
		("Pending Inventory Review", "Approve", "Approved", INVENTORY, None, 0),
		("Pending Inventory Review", "Reject", "Inventory Rejected", INVENTORY, None, 0),
		("Approved", "Acknowledge Receipt", "Completed", "Employee", f"{OWNER} and doc.status == 'Issued'", 1),
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
	# (name, field watched, condition, recipient kwargs)
	notifications = [
		(
			"Request Awaiting Manager",
			"workflow_state",
			"doc.workflow_state == 'Pending Manager Approval'",
			{"receiver_by_document_field": "sd_approver"},
		),
		(
			"Request Awaiting Inventory",
			"workflow_state",
			"doc.workflow_state == 'Pending Inventory Review'",
			{"receiver_by_role": INVENTORY},
		),
		(
			"Request Decision",
			"workflow_state",
			"doc.workflow_state in ('Manager Rejected', 'Inventory Rejected', 'Approved')",
			{"receiver_by_document_field": "owner"},
		),
		(
			"Request Issued",
			"status",
			"doc.status == 'Issued'",
			{"receiver_by_document_field": "owner"},
		),
	]
	for name, field, condition, recipient in notifications:
		n = frappe.get_doc("Notification", name) if frappe.db.exists("Notification", name) else frappe.new_doc("Notification")
		n.update(
			{
				"name": name,
				"__newname": name,
				"enabled": 1,
				"channel": "System Notification",
				"document_type": mr,
				"event": "Value Change",
				"value_changed": field,
				"condition": condition,
				"subject": "{{ doc.name }}: {{ doc.workflow_state }}",
				"message": "Inventory request {{ doc.name }} is now {{ doc.workflow_state }} ({{ doc.status }}).",
			}
		)
		n.set("recipients", [recipient])
		n.save(ignore_permissions=True)
