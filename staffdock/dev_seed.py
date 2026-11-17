"""Development seed data. Never run on staging/production.

bench --site staffdock.localhost execute staffdock.dev_seed.run --kwargs '{"password": "..."}'

Safe to re-run: existing records are left untouched.
"""

import frappe

COMPANY = "Acme Corp"
DOMAIN = "example.com"

DEPARTMENTS = ["IT", "Administration"]

# Demo people, one per role. Sign in with the part before @.
# (email, first, last, gender, department, designation, extra roles, manager email)
PEOPLE = [
	("max@example.com", "Max", "Manager", "Male", "IT", "Manager", [], None),
	("emma@example.com", "Emma", "Employee", "Female", "IT", "Software Developer", [], "max@example.com"),
	("ian@example.com", "Ian", "Inventory", "Male", "Administration", "Administrative Officer", ["Inventory"], None),
	("olivia@example.com", "Olivia", "Other", "Female", "Marketing", "Marketing Specialist", [], "ian@example.com"),
	("hana@example.com", "Hana", "HR", "Female", "Human Resources", "HR Manager", ["HR Manager", "HR User"], None),
]


def run(password):
	if not frappe.conf.developer_mode:
		frappe.throw("dev_seed runs only with developer_mode enabled")

	if not frappe.is_setup_complete():
		from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

		setup_complete(
			{
				"language": "English",
				"country": "United States",
				"timezone": "America/New_York",
				"currency": "USD",
				"company_name": COMPANY,
				"company_abbr": "AC",
				"chart_of_accounts": "Standard",
				"fy_start_date": "2026-01-01",
				"fy_end_date": "2026-12-31",
			}
		)

	frappe.db.set_single_value("StaffDock Settings", {"app_title": "StaffDock", "email_domain": DOMAIN})
	frappe.clear_document_cache("StaffDock Settings", "StaffDock Settings")

	abbr = frappe.db.get_value("Company", COMPANY, "abbr")

	for gender in ("Male", "Female"):
		_ensure("Gender", gender, gender=gender)

	for name in DEPARTMENTS:
		if not frappe.db.exists("Department", f"{name} - {abbr}"):
			frappe.get_doc(
				{"doctype": "Department", "department_name": name, "company": COMPANY, "parent_department": "All Departments"}
			).insert()

	employee_by_email = {}
	for email, first, last, gender, dept, designation, roles, _ in PEOPLE:
		if not frappe.db.exists("User", email):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": first,
					"last_name": last,
					"send_welcome_email": 0,
					"new_password": password,
				}
			).insert()
		frappe.get_doc("User", email).add_roles("Employee", *roles)

		employee = frappe.db.get_value("Employee", {"user_id": email})
		if not employee:
			employee = (
				frappe.get_doc(
					{
						"doctype": "Employee",
						"first_name": first,
						"last_name": last,
						"gender": gender,
						"date_of_birth": "1995-01-01",
						"date_of_joining": "2026-01-01",
						"company": COMPANY,
						"department": f"{dept} - {abbr}",
						"designation": designation,
						"user_id": email,
						"company_email": email,
						"prefered_contact_email": "Company Email",
					}
				)
				.insert()
				.name
			)
		employee_by_email[email] = employee

	for email, *_, manager in PEOPLE:
		if manager:
			employee = frappe.get_doc("Employee", employee_by_email[email])
			employee.reports_to = employee_by_email[manager]
			employee.save()  # also sets the leave approver (events.employee_validate)

	seed_inventory(abbr)
	seed_leave(employee_by_email.values())
	seed_announcements()

	frappe.db.commit()
	return employee_by_email


ITEM_GROUPS = ["IT Equipment", "Office Supplies", "Safety Equipment"]

# (code, name, group, uom, opening qty in Stores, rate)
STOCK_ITEMS = [
	("USB-C-CABLE", "USB-C Cable", "IT Equipment", "Nos", 30, 500),
	("A4-PAPER", "A4 Paper Ream", "Office Supplies", "Nos", 50, 650),
	("FIRST-AID-KIT", "First Aid Kit", "Safety Equipment", "Nos", 10, 2500),
	("OXYGEN-BOTTLE", "Oxygen Bottle", "Safety Equipment", "Nos", 8, 12000),
]

# (code, name, count, purchase amount)
ASSET_ITEMS = [
	("LAPTOP-MBP", "MacBook Pro", 3, 250000),
	("PHONE-ANDROID", "Android Phone", 2, 40000),
]


YEAR = str(frappe.utils.getdate().year)
# (month-day, name) — demo public holidays
PUBLIC_HOLIDAYS = [("01-01", "New Year's Day"), ("12-25", "Christmas Day"), ("12-31", "New Year's Eve")]
# (leave type, days per year)
LEAVE_ALLOCATIONS = [("Casual Leave", 12), ("Sick Leave", 6)]


def seed_leave(employees):
	holiday_list = f"{COMPANY} {YEAR}"
	if frappe.db.exists("Holiday List", holiday_list):
		hl = frappe.get_doc("Holiday List", holiday_list)
	else:
		hl = frappe.get_doc(
			{
				"doctype": "Holiday List",
				"holiday_list_name": holiday_list,
				"from_date": f"{YEAR}-01-01",
				"to_date": f"{YEAR}-12-31",
			}
		)
		for day in ("Saturday", "Sunday"):
			hl.weekly_off = day
			hl.get_weekly_off_dates()
	taken = {str(h.holiday_date) for h in hl.holidays}
	for date, description in PUBLIC_HOLIDAYS:
		if f"{YEAR}-{date}" not in taken:
			hl.append("holidays", {"holiday_date": f"{YEAR}-{date}", "description": description})
	hl.save()
	frappe.db.set_value("Company", COMPANY, "default_holiday_list", holiday_list)
	# Frappe HR v16 reads holidays from an assignment, not the company default
	if not frappe.db.exists("Holiday List Assignment", {"assigned_to": COMPANY, "docstatus": 1}):
		assignment = frappe.get_doc(
			{
				"doctype": "Holiday List Assignment",
				"applicable_for": "Company",
				"assigned_to": COMPANY,
				"holiday_list": holiday_list,
				"from_date": f"{YEAR}-01-01",
			}
		)
		assignment.insert()
		assignment.submit()

	for employee in employees:
		for leave_type, days in LEAVE_ALLOCATIONS:
			if frappe.db.exists("Leave Allocation", {"employee": employee, "leave_type": leave_type, "docstatus": 1}):
				continue
			allocation = frappe.get_doc(
				{
					"doctype": "Leave Allocation",
					"employee": employee,
					"leave_type": leave_type,
					"from_date": f"{YEAR}-01-01",
					"to_date": f"{YEAR}-12-31",
					"new_leaves_allocated": days,
				}
			)
			allocation.insert()
			allocation.submit()


def seed_announcements():
	if not frappe.db.exists("Staff Announcement", {"title": "Welcome to StaffDock"}):
		frappe.get_doc(
			{
				"doctype": "Staff Announcement",
				"title": "Welcome to StaffDock",
				"message": "<p>Requests, leave, attendance and company news now live in one place.</p>",
			}
		).insert()
	if not frappe.db.exists("Staff Policy", {"title": "Code of Conduct"}):
		frappe.get_doc(
			{
				"doctype": "Staff Policy",
				"title": "Code of Conduct",
				"version": "1",
				"effective_from": f"{YEAR}-01-01",
				"content": "<p>Treat colleagues with respect, protect company data and report concerns to HR.</p>",
			}
		).insert()


def seed_inventory(abbr):
	for group in ITEM_GROUPS:
		_ensure("Item Group", group, item_group_name=group, parent_item_group="All Item Groups")

	_ensure("Warehouse", f"IT Store - {abbr}", warehouse_name="IT Store", company=COMPANY, parent_warehouse=f"All Warehouses - {abbr}")
	_ensure("Location", "Main Office", location_name="Main Office")
	_ensure(
		"Asset Category",
		"IT Equipment",
		asset_category_name="IT Equipment",
		accounts=[
			{
				"company_name": COMPANY,
				"fixed_asset_account": f"Electronic Equipment - {abbr}",
				"accumulated_depreciation_account": f"Accumulated Depreciation - {abbr}",
				"depreciation_expense_account": f"Depreciation - {abbr}",
			}
		],
	)

	new_stock = []
	for code, name, group, uom, qty, rate in STOCK_ITEMS:
		if not frappe.db.exists("Item", code):
			_ensure("Item", code, item_code=code, item_name=name, item_group=group, stock_uom=uom, is_stock_item=1)
			new_stock.append({"item_code": code, "qty": qty, "basic_rate": rate, "t_warehouse": f"Stores - {abbr}"})
	if new_stock:
		entry = frappe.get_doc(
			{"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "company": COMPANY, "items": new_stock}
		)
		entry.insert()
		entry.submit()

	for code, name, count, amount in ASSET_ITEMS:
		_ensure(
			"Item",
			code,
			item_code=code,
			item_name=name,
			item_group="IT Equipment",
			stock_uom="Nos",
			is_stock_item=0,
			is_fixed_asset=1,
			asset_category="IT Equipment",
		)
		for i in range(1, count + 1):
			asset_name = f"{name} #{i}"
			if frappe.db.exists("Asset", {"asset_name": asset_name}):
				continue
			asset = frappe.get_doc(
				{
					"doctype": "Asset",
					"company": COMPANY,
					"item_code": code,
					"asset_name": asset_name,
					"location": "Main Office",
					"is_existing_asset": 1,
					"purchase_date": "2026-02-12",
					"available_for_use_date": "2026-02-12",
					"net_purchase_amount": amount,
					"purchase_amount": amount,
					"calculate_depreciation": 0,
				}
			)
			asset.insert()
			asset.submit()


def _ensure(doctype, name, **values):
	if not frappe.db.exists(doctype, name):
		frappe.get_doc({"doctype": doctype, **values}).insert()
