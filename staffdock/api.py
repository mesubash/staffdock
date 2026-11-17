"""Endpoints for the /staff portal. Each runs as the logged-in user, so normal
permissions and the StaffDock workflows still apply; inventory endpoints also require Inventory."""

import frappe
from erpnext.stock.doctype.material_request.material_request import make_stock_entry
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.query_builder.functions import Sum
from frappe.utils import flt

from staffdock.staffdock.doctype.staffdock_settings import staffdock_settings

INVENTORY = "Inventory"


def _company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")


def _default_warehouse():
	if configured := staffdock_settings.get().default_warehouse:
		return configured
	company = _company()
	return frappe.db.get_value("Warehouse", {"warehouse_name": "Stores", "company": company}) or frappe.db.get_value(
		"Warehouse", {"is_group": 0, "company": company}
	)


@frappe.whitelist()
def me():
	user = frappe.session.user
	roles = set(frappe.get_roles())
	employee = frappe.db.get_value(
		"Employee", {"user_id": user}, ["name", "employee_name", "department", "image"], as_dict=True
	)
	return {
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"image": (employee and employee.image) or frappe.db.get_value("User", user, "user_image"),
		"employee": employee,
		"is_manager": bool(employee and frappe.db.exists("Employee", {"reports_to": employee.name, "status": "Active"})),
		"is_approver": bool(
			frappe.db.exists("Employee", {"leave_approver": user, "status": "Active"})
			or frappe.db.exists("Employee", {"expense_approver": user, "status": "Active"})
		),
		"is_inventory": INVENTORY in roles,
		"has_desk": frappe.db.get_value("User", user, "user_type") == "System User",
		"default_warehouse": _default_warehouse(),
		"date_format": frappe.db.get_default("date_format") or "yyyy-mm-dd",
	}


@frappe.whitelist()
def issue_request(name):
	"""Issue an approved request from stores (Material Issue stock entry)."""
	frappe.only_for(INVENTORY)
	entry = make_stock_entry(name)
	for row in entry.items:
		row.s_warehouse = row.s_warehouse or _default_warehouse()
	entry.insert()
	entry.submit()
	return entry.name


@frappe.whitelist()
def receive_stock(item_code, qty, rate=0, warehouse=None):
	"""Add stock to a store (Material Receipt), e.g. a delivery that arrived."""
	frappe.only_for(INVENTORY)
	if flt(qty) <= 0:
		frappe.throw(_("Quantity must be more than zero."))
	entry = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": _company(),
			"items": [
				{
					"item_code": item_code,
					"qty": flt(qty),
					"basic_rate": flt(rate),
					"t_warehouse": warehouse or _default_warehouse(),
				}
			],
		}
	)
	entry.insert()
	entry.submit()
	return entry.name


@frappe.whitelist()
def stock_levels():
	frappe.only_for(INVENTORY)
	bins = frappe.get_all("Bin", fields=["item_code", "warehouse", "actual_qty", "reserved_qty"], order_by="item_code")
	names = dict(frappe.get_all("Item", fields=["name", "item_name"], as_list=True))
	for b in bins:
		b["item_name"] = names.get(b["item_code"], b["item_code"])
	return bins


@frappe.whitelist()
def employees():
	"""Active employees to issue assets to."""
	frappe.only_for(INVENTORY)
	return frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "department"],
		order_by="employee_name",
		ignore_permissions=True,
	)


@frappe.whitelist()
def issue_asset(asset, employee):
	"""Hand an asset to an employee; it waits for their acknowledgement."""
	frappe.only_for(INVENTORY)
	doc = frappe.get_doc("Asset", asset)
	if doc.custodian:
		frappe.throw(_("{0} is already with {1}. Receive it back first.").format(doc.asset_name, doc.custodian))
	movement = frappe.get_doc(
		{
			"doctype": "Asset Movement",
			"company": doc.company,
			"purpose": "Issue",
			"assets": [{"asset": asset, "source_location": doc.location, "to_employee": employee}],
		}
	).insert()
	apply_workflow(movement, "Issue")
	return movement.name


@frappe.whitelist()
def receive_asset(asset, condition, location=None):
	"""Take an asset back from its custodian and record its condition."""
	frappe.only_for(INVENTORY)
	doc = frappe.get_doc("Asset", asset)
	if not doc.custodian:
		frappe.throw(_("{0} is not with anyone.").format(doc.asset_name))
	movement = frappe.get_doc(
		{
			"doctype": "Asset Movement",
			"company": doc.company,
			"purpose": "Receipt",
			"sd_return_condition": condition,
			"assets": [
				{
					"asset": asset,
					"from_employee": doc.custodian,
					"target_location": location or doc.location or frappe.db.get_value("Location", {}, "name"),
				}
			],
		}
	).insert()
	apply_workflow(movement, "Submit")
	return movement.name


@frappe.whitelist()
def my_tasks():
	"""Everything waiting on the current user, for the portal home page."""
	user = frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	fields = ["name", "sd_employee_name", "sd_reason", "workflow_state", "status", "modified"]
	request = frappe.qb.DocType("Asset Movement")
	item = frappe.qb.DocType("Asset Movement Item")
	tasks = {
		"to_approve": frappe.get_all(
			"Material Request",
			filters={"sd_approver": user, "workflow_state": "Pending Manager Approval"},
			fields=fields,
		),
		"requests_to_acknowledge": frappe.get_all(
			"Material Request",
			filters={"owner": user, "workflow_state": "Approved", "status": "Issued"},
			fields=fields,
		),
		"assets_to_acknowledge": (
			frappe.qb.from_(request)
			.join(item)
			.on(item.parent == request.name)
			.select(request.name, item.asset, item.asset_name, request.modified)
			.where((request.workflow_state == "Pending Acknowledgement") & (item.to_employee == employee))
			.run(as_dict=True)
			if employee
			else []
		),
		"open_requests": frappe.db.count(
			"Material Request", {"owner": user, "workflow_state": ["not in", ["Completed", "Inventory Rejected"]]}
		),
		"my_assets": frappe.db.count("Asset", {"custodian": employee}) if employee else 0,
		"leaves_to_approve": leaves_to_approve(),
		"expenses_to_approve": frappe.get_all(
			"Expense Claim",
			filters={"expense_approver": user, "approval_status": "Draft", "docstatus": 0},
			fields=["name", "employee_name", "total_claimed_amount", "currency"],
		),
		"policies_to_acknowledge": _policies_to_acknowledge(employee),
	}
	if INVENTORY in frappe.get_roles():
		tasks["to_review"] = frappe.get_all(
			"Material Request", filters={"workflow_state": "Pending Inventory Review"}, fields=fields
		)
		tasks["to_issue"] = frappe.get_all(
			"Material Request",
			filters={"workflow_state": "Approved", "status": ["!=", "Issued"]},
			fields=fields,
		)
	return tasks


HISTORY_DOCTYPES = ("Material Request", "Asset Movement")


@frappe.whitelist()
def history(doctype, name):
	"""Who did what and when: creation, workflow steps, and stock issued against a request."""
	if doctype not in HISTORY_DOCTYPES:
		frappe.throw(_("History is not available for {0}.").format(doctype))
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")

	events = [{"at": doc.creation, "by": doc.owner, "text": _("Created")}]
	for v in frappe.get_all(
		"Version", filters={"ref_doctype": doctype, "docname": name}, fields=["owner", "creation", "data"]
	):
		for field, old, new in frappe.parse_json(v.data).get("changed", []):
			if field == "workflow_state" and old != new:
				events.append({"at": v.creation, "by": v.owner, "text": new})

	if doctype == "Material Request":
		entry = frappe.qb.DocType("Stock Entry")
		row = frappe.qb.DocType("Stock Entry Detail")
		for e in (
			frappe.qb.from_(entry)
			.join(row)
			.on(row.parent == entry.name)
			.select(entry.owner, entry.modified, Sum(row.qty).as_("qty"))
			.where((row.material_request == name) & (entry.docstatus == 1))
			.groupby(entry.name)
			.run(as_dict=True)
		):
			events.append({"at": e.modified, "by": e.owner, "text": _("Issued {0} item(s) from store").format(f"{flt(e.qty):g}")})

	for e in events:
		e["by"] = frappe.utils.get_fullname(e["by"])
	return sorted(events, key=lambda e: e["at"])


@frappe.whitelist()
def discard_request(name):
	"""Delete your own request that was never sent."""
	doc = frappe.get_doc("Material Request", name)
	if doc.owner != frappe.session.user or doc.docstatus != 0 or doc.workflow_state not in (None, "", "Draft"):
		frappe.throw(_("Only your own unsent requests can be discarded."), frappe.PermissionError)
	frappe.delete_doc("Material Request", name, ignore_permissions=True)


@frappe.whitelist()
def updates(limit=10):
	"""Latest notifications for the current user (approvals, decisions, issues, assets)."""
	return frappe.get_all(
		"Notification Log",
		filters={"for_user": frappe.session.user},
		fields=["subject", "document_type", "document_name", "creation", "read"],
		order_by="creation desc",
		limit=min(int(limit), 50),
	)


# --- Leave (Frappe HR Leave Application)

LEAVE_FIELDS = [
	"name",
	"employee_name",
	"leave_type",
	"from_date",
	"to_date",
	"half_day",
	"total_leave_days",
	"description",
	"status",
	"docstatus",
	"leave_approver_name",
	"modified",
]


def _department_name(department):
	"""ERPNext suffixes departments with the company abbreviation ("IT - AC"); show the plain name."""
	return department and (frappe.db.get_value("Department", department, "department_name") or department)


def _my_employee():
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("Your account is not linked to an employee record. Contact HR."))
	return employee


@frappe.whitelist()
def leave_summary():
	"""Balances per leave type and my applications, newest first."""
	from hrms.hr.doctype.leave_application.leave_application import get_leave_details

	employee = _my_employee()
	allocation = get_leave_details(employee, frappe.utils.today())["leave_allocation"]
	return {
		"balances": [
			{
				"leave_type": leave_type,
				"total": flt(d.get("total_leaves")),
				"taken": flt(d.get("leaves_taken")),
				"pending": flt(d.get("leaves_pending_approval")),
				"remaining": flt(d.get("remaining_leaves")),
			}
			for leave_type, d in allocation.items()
		],
		"applications": frappe.get_all(
			"Leave Application",
			filters={"employee": employee},
			fields=LEAVE_FIELDS,
			order_by="from_date desc",
			limit=50,
		),
	}


@frappe.whitelist()
def apply_leave(leave_type, from_date, to_date, reason, half_day=0):
	employee = _my_employee()
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"half_day": frappe.utils.cint(half_day),
			"half_day_date": from_date if frappe.utils.cint(half_day) else None,
			"description": reason,
			"status": "Open",
		}
	)
	if not doc.leave_approver:
		from hrms.hr.doctype.leave_application.leave_application import get_employee_leave_approver

		doc.leave_approver = get_employee_leave_approver(employee)
	if not doc.leave_approver:
		frappe.throw(_("You have no leave approver. Ask HR to set your manager."))
	doc.insert()
	return doc.name


@frappe.whitelist()
def withdraw_leave(name):
	"""Take back your own leave application before it is decided."""
	doc = frappe.get_doc("Leave Application", name)
	if doc.employee != _my_employee() or doc.docstatus != 0 or doc.status != "Open":
		frappe.throw(_("Only your own undecided leave can be withdrawn."), frappe.PermissionError)
	frappe.delete_doc("Leave Application", name, ignore_permissions=True)


@frappe.whitelist()
def leaves_to_approve():
	return frappe.get_all(
		"Leave Application",
		filters={"leave_approver": frappe.session.user, "status": "Open", "docstatus": 0},
		fields=LEAVE_FIELDS,
		order_by="from_date asc",
	)


@frappe.whitelist()
def decide_leave(name, approve):
	"""Approve or reject as the leave approver. HRMS records both by submitting."""
	doc = frappe.get_doc("Leave Application", name)
	if doc.leave_approver != frappe.session.user:
		frappe.throw(_("Only the leave approver can decide this application."), frappe.PermissionError)
	if doc.docstatus != 0 or doc.status != "Open":
		frappe.throw(_("This leave application is already decided."))
	doc.status = "Approved" if frappe.utils.cint(approve) else "Rejected"
	# The approver check above replaces row-level access: approvers can't read other
	# employees' records through Employee user permissions.
	doc.flags.ignore_permissions = True
	doc.submit()
	return doc.status


# --- Attendance (Frappe HR Employee Checkin). Time always comes from the server.

DOUBLE_TAP_SECONDS = 10


def _checkins(employee, start, end):
	return frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [start, end]]},
		fields=["log_type", "time"],
		order_by="time asc",
	)


def _worked_seconds(logs, until=None):
	"""Sum IN→OUT pairs; an open IN counts up to `until` (now, for today)."""
	total, started = 0, None
	for log in logs:
		if log.log_type == "IN" and started is None:
			started = log.time
		elif log.log_type == "OUT" and started is not None:
			total += (log.time - started).total_seconds()
			started = None
	if started is not None and until:
		total += (until - started).total_seconds()
	return int(total)


@frappe.whitelist()
def attendance_today():
	employee = _my_employee()
	now = frappe.utils.now_datetime()
	day = now.date()
	logs = _checkins(employee, f"{day} 00:00:00", f"{day} 23:59:59")
	checked_in = bool(logs) and logs[-1].log_type == "IN"
	return {
		"checked_in": checked_in,
		"first_in": next((l.time for l in logs if l.log_type == "IN"), None),
		"last": logs[-1].time if logs else None,
		"worked_seconds": _worked_seconds(logs, now),
		"geolocation_required": bool(frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking")),
	}


@frappe.whitelist()
def check_in_out(latitude=None, longitude=None):
	"""Toggle: check in if out, check out if in. Employees can't create check-ins any other way."""
	employee = _my_employee()
	now = frappe.utils.now_datetime()
	day = now.date()
	logs = _checkins(employee, f"{day} 00:00:00", f"{day} 23:59:59")
	if logs and (now - logs[-1].time).total_seconds() < DOUBLE_TAP_SECONDS:
		return logs[-1].log_type  # double click: keep the state the first click set
	log_type = "OUT" if logs and logs[-1].log_type == "IN" else "IN"
	frappe.get_doc(
		{
			"doctype": "Employee Checkin",
			"employee": employee,
			"log_type": log_type,
			"time": now,
			"latitude": flt(latitude) or None,
			"longitude": flt(longitude) or None,
		}
	).insert(ignore_permissions=True)
	return log_type


@frappe.whitelist()
def attendance_history(days=30):
	employee = _my_employee()
	end = frappe.utils.now_datetime()
	start = frappe.utils.add_days(end.date(), -min(int(days), 90) + 1)
	by_day = {}
	for log in _checkins(employee, f"{start} 00:00:00", end):
		by_day.setdefault(log.time.date(), []).append(log)
	today = end.date()
	return [
		{
			"date": day,
			"first_in": next((l.time for l in logs if l.log_type == "IN"), None),
			"last_out": next((l.time for l in reversed(logs) if l.log_type == "OUT"), None),
			"worked_seconds": _worked_seconds(logs, end if day == today else None),
		}
		for day, logs in sorted(by_day.items(), reverse=True)
	]


# --- My profile. Employees can't write their Employee record directly; only these fields change.

PROFILE_FIELDS = (
	"employee_name",
	"designation",
	"department",
	"company",
	"date_of_joining",
	"company_email",
	"image",
	"cell_number",
	"personal_email",
	"current_address",
	"person_to_be_contacted",
	"emergency_phone_number",
	"relation",
)
PROFILE_EDITABLE = (
	"cell_number",
	"personal_email",
	"current_address",
	"person_to_be_contacted",
	"emergency_phone_number",
	"relation",
)


@frappe.whitelist()
def my_profile():
	employee = frappe.get_doc("Employee", _my_employee())
	profile = {f: employee.get(f) for f in PROFILE_FIELDS}
	profile["department"] = _department_name(employee.department)
	profile["manager"] = employee.reports_to and frappe.db.get_value("Employee", employee.reports_to, "employee_name")
	return profile


@frappe.whitelist()
def update_profile(**changes):
	employee = frappe.get_doc("Employee", _my_employee())
	for field in PROFILE_EDITABLE:
		if field in changes:
			employee.set(field, (changes[field] or "").strip())
	if employee.personal_email:
		frappe.utils.validate_email_address(employee.personal_email, throw=True)
	employee.flags.ignore_permissions = True
	employee.save()
	return my_profile()


@frappe.whitelist()
def set_profile_photo(file_url):
	"""Use an image the current user just uploaded as their photo."""
	file = frappe.db.get_value(
		"File", {"file_url": file_url, "owner": frappe.session.user}, ["name", "is_private", "file_name"], as_dict=True
	)
	if not file or not frappe.utils.is_image(file.file_name or file_url):
		frappe.throw(_("Upload an image first."))
	if file.is_private:
		frappe.throw(_("Profile photos must be public."))
	employee = frappe.get_doc("Employee", _my_employee())
	employee.image = file_url
	employee.flags.ignore_permissions = True
	employee.save()
	frappe.db.set_value("User", frappe.session.user, "user_image", file_url)
	return file_url


# --- People: directory, who's out today, upcoming holidays. Work contact details only.


@frappe.whitelist()
def people():
	from hrms.utils.holiday_list import get_holiday_list_for_employee

	today = frappe.utils.today()
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "designation", "department", "company_email", "image"],
		order_by="employee_name asc",
		ignore_permissions=True,
	)
	departments = {
		d.name: d.department_name for d in frappe.get_all("Department", fields=["name", "department_name"])
	}
	for e in employees:
		e.department = departments.get(e.department, e.department)

	# Who's away: approved leave covering today. The leave type stays private.
	out = frappe.get_all(
		"Leave Application",
		filters={"status": "Approved", "docstatus": 1, "from_date": ["<=", today], "to_date": [">=", today]},
		fields=["employee", "to_date"],
		ignore_permissions=True,
	)
	by_id = {e.name: e for e in employees}
	out_today = [
		{"employee_name": by_id[o.employee].employee_name, "image": by_id[o.employee].image, "back_after": o.to_date}
		for o in out
		if o.employee in by_id
	]

	holidays = []
	holiday_list = get_holiday_list_for_employee(_my_employee(), raise_exception=False)
	if holiday_list:
		holidays = frappe.get_all(
			"Holiday",
			filters={"parent": holiday_list, "holiday_date": [">=", today], "weekly_off": 0},
			fields=["holiday_date", "description"],
			order_by="holiday_date asc",
			limit=5,
		)
		for h in holidays:
			h.description = frappe.utils.strip_html(h.description or "")

	return {"employees": employees, "out_today": out_today, "holidays": holidays}


# --- Announcements and policies (HR writes them in desk; staff read and acknowledge here)


def _clean_html(html):
	from frappe.utils.html_utils import sanitize_html

	return sanitize_html(html or "")


@frappe.whitelist()
def announcements(limit=5):
	rows = frappe.get_all(
		"Staff Announcement",
		filters={"published": 1},
		fields=["name", "title", "message", "creation"],
		order_by="creation desc",
		limit=min(int(limit), 20),
	)
	for r in rows:
		r.message = _clean_html(r.message)
	return rows


def _acknowledged(employee):
	"""{(policy, version)} pairs the employee has acknowledged; a new version needs a new acknowledgement."""
	if not employee:
		return set()
	return {
		tuple(row)
		for row in frappe.get_all(
			"Staff Policy Acknowledgement", filters={"employee": employee}, fields=["policy", "version"], as_list=True
		)
	}


def _policies_to_acknowledge(employee):
	done = _acknowledged(employee)
	return [
		p
		for p in frappe.get_all(
			"Staff Policy",
			filters={"published": 1, "requires_acknowledgement": 1},
			fields=["name", "title", "version"],
		)
		if (p.name, p.version) not in done
	]


@frappe.whitelist()
def policies():
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	done = _acknowledged(employee)
	rows = frappe.get_all(
		"Staff Policy",
		filters={"published": 1},
		fields=["name", "title", "version", "effective_from", "requires_acknowledgement", "content"],
		order_by="title asc",
	)
	for r in rows:
		r.content = _clean_html(r.content)
		r.acknowledged = (r.name, r.version) in done
	return rows


@frappe.whitelist()
def acknowledge_policy(name):
	employee = _my_employee()
	policy = frappe.db.get_value("Staff Policy", {"name": name, "published": 1}, ["name", "version"], as_dict=True)
	if not policy:
		frappe.throw(_("Policy not found."))
	if (policy.name, policy.version) not in _acknowledged(employee):
		frappe.get_doc(
			{
				"doctype": "Staff Policy Acknowledgement",
				"policy": policy.name,
				"version": policy.version,
				"employee": employee,
				"acknowledged_on": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
	return True


# --- Expenses (Frappe HR Expense Claim). Finance pays approved claims in desk as usual.

EXPENSE_FIELDS = [
	"name",
	"employee_name",
	"posting_date",
	"total_claimed_amount",
	"total_sanctioned_amount",
	"approval_status",
	"status",
	"docstatus",
	"remark",
	"currency",
	"expense_approver",
]


def _with_lines(claims):
	for c in claims:
		c.lines = frappe.get_all(
			"Expense Claim Detail",
			filters={"parent": c.name},
			fields=["expense_date", "expense_type", "description", "amount"],
			order_by="idx asc",
		)
		c.receipts = frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Expense Claim", "attached_to_name": c.name},
			fields=["file_name", "file_url"],
		)
	return claims


@frappe.whitelist()
def my_expenses():
	return {
		"types": frappe.get_all("Expense Claim Type", pluck="name", order_by="name asc"),
		"claims": _with_lines(
			frappe.get_all(
				"Expense Claim",
				filters={"employee": _my_employee(), "docstatus": ["<", 2]},
				fields=EXPENSE_FIELDS,
				order_by="creation desc",
				limit=50,
			)
		),
	}


@frappe.whitelist()
def submit_expense(lines, remark="", receipt_url=None):
	"""Create a claim for the current employee; it waits for their expense approver."""
	from hrms.hr.doctype.expense_claim.expense_claim import get_default_payable_account

	employee = frappe.get_doc("Employee", _my_employee())
	lines = frappe.parse_json(lines) or []
	if not lines:
		frappe.throw(_("Add at least one expense."))
	approver = employee.expense_approver or (
		employee.reports_to and frappe.db.get_value("Employee", employee.reports_to, "user_id")
	)
	if not approver:
		frappe.throw(_("You have no expense approver. Ask HR to set your manager."))
	cost_center = frappe.get_cached_value("Company", employee.company, "cost_center")
	claim = frappe.get_doc(
		{
			"doctype": "Expense Claim",
			"employee": employee.name,
			"company": employee.company,
			"expense_approver": approver,
			"approval_status": "Draft",
			"remark": remark,
			"payable_account": get_default_payable_account(employee.company),
			"expenses": [
				{
					"expense_date": line.get("expense_date"),
					"expense_type": line.get("expense_type"),
					"description": line.get("description"),
					"amount": flt(line.get("amount")),
					"cost_center": cost_center,
				}
				for line in lines
			],
		}
	)
	claim.insert()
	if receipt_url:
		_attach_own_file(receipt_url, "Expense Claim", claim.name)
	return claim.name


def _attach_own_file(file_url, doctype, name):
	file = frappe.db.get_value("File", {"file_url": file_url, "owner": frappe.session.user, "attached_to_name": ["is", "not set"]})
	if not file:
		frappe.throw(_("Upload the receipt again."))
	frappe.db.set_value("File", file, {"attached_to_doctype": doctype, "attached_to_name": name})


@frappe.whitelist()
def withdraw_expense(name):
	claim = frappe.get_doc("Expense Claim", name)
	if claim.employee != _my_employee() or claim.docstatus != 0 or claim.approval_status != "Draft":
		frappe.throw(_("Only your own undecided claims can be withdrawn."), frappe.PermissionError)
	frappe.delete_doc("Expense Claim", name, ignore_permissions=True)


@frappe.whitelist()
def expenses_to_approve():
	return _with_lines(
		frappe.get_all(
			"Expense Claim",
			filters={"expense_approver": frappe.session.user, "approval_status": "Draft", "docstatus": 0},
			fields=EXPENSE_FIELDS,
			order_by="posting_date asc",
		)
	)


@frappe.whitelist()
def decide_expense(name, approve):
	claim = frappe.get_doc("Expense Claim", name)
	if claim.expense_approver != frappe.session.user:
		frappe.throw(_("Only the expense approver can decide this claim."), frappe.PermissionError)
	if claim.docstatus != 0 or claim.approval_status != "Draft":
		frappe.throw(_("This claim is already decided."))
	approved = frappe.utils.cint(approve)
	claim.approval_status = "Approved" if approved else "Rejected"
	for line in claim.expenses:
		line.sanctioned_amount = line.amount if approved else 0
	# Explicit approver check above; approvers can't otherwise reach other employees' records
	claim.flags.ignore_permissions = True
	claim.submit()
	return claim.approval_status
