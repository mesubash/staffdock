import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name


def material_request_validate(doc, method=None):
	"""Stamp requester and their reporting manager's user on new requests."""
	if not doc.is_new():
		return
	employee = frappe.db.get_value(
		"Employee", {"user_id": doc.owner}, ["name", "employee_name", "reports_to"], as_dict=True
	)
	if not employee:
		return
	doc.sd_employee = employee.name
	doc.sd_employee_name = employee.employee_name
	if employee.reports_to:
		doc.sd_approver = frappe.db.get_value("Employee", employee.reports_to, "user_id")


def require_workflow_submit(doc, method=None):
	"""Block submitting outside the workflow (e.g. a direct frappe.client.submit call)."""
	workflow = get_workflow_name(doc.doctype)
	if not workflow:
		return
	# ERPNext submits Receipt movements itself when an asset is created; only Issue needs
	# the employee acknowledgement path, so other purposes just complete.
	if doc.doctype == "Asset Movement" and doc.purpose != "Issue":
		doc.workflow_state = "Completed"
		return
	doc_status = frappe.db.get_value(
		"Workflow Document State", {"parent": workflow, "state": doc.workflow_state}, "doc_status"
	)
	if str(doc_status) != "1":
		frappe.throw(_("Use the workflow actions to submit this document."), frappe.PermissionError)


def asset_movement_on_submit(doc, method=None):
	"""In-app notification to each employee receiving an asset."""
	for row in doc.assets:
		user = row.to_employee and frappe.db.get_value("Employee", row.to_employee, "user_id")
		if not user:
			continue
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": _("Asset {0} assigned to you. Please acknowledge receipt.").format(row.asset),
			}
		).insert(ignore_permissions=True)
