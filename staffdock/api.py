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
	employee = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name", "department"], as_dict=True)
	return {
		"user": user,
		"full_name": frappe.utils.get_fullname(user),
		"employee": employee,
		"is_manager": bool(employee and frappe.db.exists("Employee", {"reports_to": employee.name, "status": "Active"})),
		"is_inventory": INVENTORY in roles,
		"has_desk": frappe.db.get_value("User", user, "user_type") == "System User",
		"default_warehouse": _default_warehouse(),
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
