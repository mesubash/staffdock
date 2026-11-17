import frappe
from frappe import _
from frappe.model.workflow import get_workflow_name

from staffdock.staffdock.doctype.staffdock_settings import staffdock_settings


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
		doc.sd_approver_name = frappe.utils.get_fullname(doc.sd_approver) if doc.sd_approver else None


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
		subject = _("{0} was assigned to you. Please confirm you received it").format(row.asset_name or row.asset)
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"document_type": doc.doctype,
				"document_name": doc.name,
				"subject": subject,
			}
		).insert(ignore_permissions=True)
		if staffdock_settings.get().send_email_notifications:
			frappe.sendmail(
				recipients=[user],
				subject=subject,
				message=f'<p>{subject}</p><p><a href="{frappe.utils.get_url("/staff/assets")}">Open StaffDock</a></p>',
			)


# People who manage other employees' records must not be limited to their own Employee record.
HR_ROLES = {"HR Manager", "HR User", "System Manager"}


def employee_validate(doc, method=None):
	"""The reporting manager approves leave and expenses unless HR set different approvers."""
	if doc.reports_to:
		manager_user = frappe.db.get_value("Employee", doc.reports_to, "user_id")
		doc.leave_approver = doc.leave_approver or manager_user
		doc.expense_approver = doc.expense_approver or manager_user
	if doc.user_id and HR_ROLES & set(frappe.get_roles(doc.user_id)):
		# ERPNext removes the existing "own record only" user permission when this changes
		doc.create_user_permission = 0


def user_on_update(doc, method=None):
	"""Someone given an HR role later: lift the own-record restriction on their employee."""
	if not HR_ROLES & {r.role for r in doc.roles}:
		return
	for employee in frappe.get_all("Employee", filters={"user_id": doc.name, "create_user_permission": 1}, pluck="name"):
		frappe.get_doc("Employee", employee).save(ignore_permissions=True)
