"""End-to-end check of the inventory MVP against a running dev site.

python3 scripts/e2e_check.py   (reads test password from development/site-credentials.txt)

Creates new records each run. Dev only.
"""

import http.cookiejar
import json
import pathlib
import re
import time
import urllib.error
import urllib.request

BASE = "http://staffdock.localhost:8000"
CREDS = dict(
	line.split("=", 1) for line in (pathlib.Path(__file__).parent.parent / "development/site-credentials.txt").read_text().split()
)
PW = CREDS["test_password"]
ADMIN_PW = CREDS["password"]


class Session:
	def __init__(self, user, password=None):
		self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
		self.csrf = ""
		self.call("POST", "/api/method/login", {"usr": user, "pwd": password or PW})
		# Same as the browser: the portal page hands out the session's CSRF token
		page = self.opener.open(BASE + "/staff").read().decode()
		self.csrf = re.search(r'csrf_token = "([^"]*)"', page).group(1)

	def call(self, method, path, data=None):
		req = urllib.request.Request(
			BASE + path.replace(" ", "%20"),
			method=method,
			data=json.dumps(data).encode() if data is not None else None,
			headers={"Content-Type": "application/json", "Accept": "application/json", "X-Frappe-CSRF-Token": self.csrf},
		)
		try:
			with self.opener.open(req) as r:
				body = json.loads(r.read() or "{}")
		except urllib.error.HTTPError as e:
			e.msg = f"{method} {path}: {e.read()[:400].decode(errors='replace')}"
			raise
		return body.get("message", body.get("data"))

	def ok(self, *a):
		try:
			self.call(*a)
			return True
		except urllib.error.HTTPError:
			return False

	def get(self, doctype, name):
		return self.call("GET", f"/api/resource/{doctype}/{name}")

	def names(self, doctype):
		return {d["name"] for d in self.call("GET", f"/api/resource/{doctype}?limit_page_length=500")}

	def status(self, path):
		try:
			with self.opener.open(BASE + path) as r:
				return r.status, r.geturl()
		except urllib.error.HTTPError as e:
			return e.code, path

	def upload(self, name, content, is_private=0, doctype=None, docname=None):
		boundary = "----staffdock" + str(time.time_ns())
		attach = (
			f"--{boundary}\r\nContent-Disposition: form-data; name=\"doctype\"\r\n\r\n{doctype}\r\n"
			f"--{boundary}\r\nContent-Disposition: form-data; name=\"docname\"\r\n\r\n{docname}\r\n"
			if doctype
			else ""
		)
		body = (
			attach + f"--{boundary}\r\nContent-Disposition: form-data; name=\"is_private\"\r\n\r\n{is_private}\r\n"
			f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{name}\"\r\n"
			"Content-Type: application/octet-stream\r\n\r\n"
		).encode() + content + f"\r\n--{boundary}--\r\n".encode()
		req = urllib.request.Request(
			BASE + "/api/method/upload_file",
			data=body,
			method="POST",
			headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "X-Frappe-CSRF-Token": self.csrf, "Accept": "application/json"},
		)
		with self.opener.open(req) as r:
			return json.loads(r.read())["message"]["file_url"]

	def api(self, method, **args):
		return self.call("POST", f"/api/method/staffdock.api.{method}", args)

	def act(self, doctype, name, action):
		doc = self.get(doctype, name)
		return self.call("POST", "/api/method/frappe.model.workflow.apply_workflow", {"doc": doc, "action": action})


emma, max, ian, olivia = (
	Session(f"{u}@example.com") for u in ("emma", "max", "ian", "olivia")
)
WORKFLOW = "/api/method/frappe.model.workflow.apply_workflow"

hana = Session("hana@example.com")

# --- Sign-in is Frappe's own page, branded from StaffDock Settings
login_page = urllib.request.urlopen(BASE + "/login").read().decode()
assert "/assets/staffdock/images/logo.svg" in login_page, "login page must carry the StaffDock logo"

# --- Staff are portal-only: desk and site home send them to /staff; HR keeps desk
for s in (emma, max, ian, olivia):
	for path in ("/", "/desk", "/desk/material-request", "/login"):
		code, url = s.status(path)
		assert code == 200 and url.endswith("/staff"), f"staff {path} must land on portal ({code} {url})"
assert hana.status("/desk")[1].endswith("/desk"), "HR keeps desk"
assert hana.api("me")["has_desk"]
assert emma.status("/staff")[0] == 200
me = emma.api("me")
assert not me["is_inventory"] and not me["has_desk"] and me["employee"]["employee_name"] == "Emma Employee"
assert max.api("me")["is_manager"] and ian.api("me")["is_inventory"]
assert not emma.ok("POST", "/api/method/staffdock.api.stock_levels", {}), "employee must not see stock levels"

# Close approved-but-unissued test requests left by earlier runs
for r in ian.api("my_tasks")["to_issue"]:
	if (r["sd_reason"] or "").startswith("e2e"):
		ian.act("Material Request", r["name"], "Close")

# --- Inventory request: employee -> manager -> inventory -> issue -> acknowledge
mr = emma.call(
	"POST",
	"/api/resource/Material Request",
	{
		"material_request_type": "Material Issue",
		"schedule_date": "2026-12-31",
		"sd_reason": "e2e check",
		"items": [{"item_code": "USB-C-CABLE", "qty": 2, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}],
	},
)
name = mr["name"]
assert mr["sd_approver"] == "max@example.com" and mr["sd_employee_name"] == "Emma Employee"
assert mr["sd_approver_name"] == "Max Manager" and name.startswith("REQ-"), (name, mr["sd_approver_name"])

bypass = emma.call(
	"POST",
	"/api/resource/Material Request",
	{"schedule_date": "2026-12-31", "items": [{"item_code": "A4-PAPER", "qty": 1, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}]},
)
assert not emma.ok("POST", "/api/method/frappe.client.submit", {"doc": emma.get("Material Request", bypass["name"])}), "must not skip workflow"
assert not olivia.ok("POST", "/api/method/staffdock.api.discard_request", {"name": bypass["name"]}), "only the owner discards"
emma.api("discard_request", name=bypass["name"])
assert not emma.ok("GET", f"/api/resource/Material Request/{bypass['name']}"), "discarded draft is gone"

assert emma.act("Material Request", name, "Submit")["workflow_state"] == "Pending Manager Approval"
assert not emma.ok("POST", WORKFLOW, {"doc": emma.get("Material Request", name), "action": "Approve"}), "self-approval must fail"
assert name not in olivia.names("Material Request"), "other team must not see request"
assert not olivia.ok("GET", f"/api/resource/Material Request/{name}"), "other team must not open request"
assert any(t["name"] == name for t in max.api("my_tasks")["to_approve"]), "manager sees it in tasks"
assert [t["action"] for t in emma.call("POST", "/api/method/frappe.model.workflow.get_transitions", {"doc": emma.get("Material Request", name)})] == [], "requester gets no buttons while waiting"

assert max.act("Material Request", name, "Approve")["workflow_state"] == "Pending Inventory Review"
assert any(t["name"] == name for t in ian.api("my_tasks")["to_review"])
assert ian.act("Material Request", name, "Approve")["workflow_state"] == "Approved"
assert not emma.ok("POST", "/api/method/staffdock.api.issue_request", {"name": name}), "employee must not issue"

ian.api("receive_stock", item_code="USB-C-CABLE", qty=2, rate=500)  # keep demo stock level across runs
before = {(b["item_code"], b["warehouse"]): b["actual_qty"] for b in ian.api("stock_levels")}
entry = ian.api("issue_request", name=name)
after = {(b["item_code"], b["warehouse"]): b["actual_qty"] for b in ian.api("stock_levels")}
assert after[("USB-C-CABLE", "Stores - AC")] == before[("USB-C-CABLE", "Stores - AC")] - 2, "stock must drop by 2"
assert any(t["name"] == name for t in emma.api("my_tasks")["requests_to_acknowledge"])
assert emma.act("Material Request", name, "Acknowledge Receipt")["workflow_state"] == "Completed"
steps = [(e["text"], e["by"]) for e in emma.api("history", doctype="Material Request", name=name)]
assert steps[0] == ("Created", "Emma Employee")
assert ("Pending Inventory Review", "Max Manager") in steps and ("Approved", "Ian Inventory") in steps
assert ("Issued 2 item(s) from store", "Ian Inventory") in steps and steps[-1] == ("Completed", "Emma Employee"), steps
assert not olivia.ok("POST", "/api/method/staffdock.api.history", {"doctype": "Material Request", "name": name}), "history follows doc access"

# --- Rejection path
rej = emma.call(
	"POST",
	"/api/resource/Material Request",
	{"schedule_date": "2026-12-31", "sd_reason": "e2e reject", "items": [{"item_code": "A4-PAPER", "qty": 1, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}]},
)
emma.act("Material Request", rej["name"], "Submit")
assert max.act("Material Request", rej["name"], "Reject")["workflow_state"] == "Manager Rejected"
assert emma.call("POST", "/api/method/frappe.model.workflow.get_transitions", {"doc": emma.get("Material Request", rej["name"])}) == [], "rejection is final"
assert not emma.ok("POST", "/api/method/staffdock.api.discard_request", {"name": rej["name"]}), "sent requests cannot be discarded"

# --- Updates feed tells each person what happened (notifications are written after commit)
def eventually(check):
	for _ in range(90):
		if check():
			return True
		time.sleep(0.5)
	return False


def eventually_updated(session, text):
	# Notifications go through the background worker; under load that can take ~30s
	for _ in range(90):
		if any(text in u["subject"] for u in session.api("updates", limit=50)):
			return True
		time.sleep(0.5)
	return False


assert eventually_updated(max, f"Emma Employee needs your approval for {name}")
assert eventually_updated(emma, f"Items for {name} were issued")
assert eventually_updated(emma, f"Your request {rej['name']} was rejected")

# --- Issuing more than is in stock fails with a readable message
big = emma.call(
	"POST",
	"/api/resource/Material Request",
	{"schedule_date": "2026-12-31", "sd_reason": "e2e too many", "items": [{"item_code": "OXYGEN-BOTTLE", "qty": 999, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}]},
)
emma.act("Material Request", big["name"], "Submit")
max.act("Material Request", big["name"], "Approve")
ian.act("Material Request", big["name"], "Approve")
try:
	ian.api("issue_request", name=big["name"])
	raise AssertionError("over-issue must fail")
except urllib.error.HTTPError as err:
	assert "needed" in err.msg, err.msg
assert [t["action"] for t in emma.call("POST", "/api/method/frappe.model.workflow.get_transitions", {"doc": emma.get("Material Request", big["name"])})] == [], "only inventory closes"
assert ian.act("Material Request", big["name"], "Close")["workflow_state"] == "Closed"
assert all(r["name"] != big["name"] for r in ian.api("my_tasks")["to_issue"]), "closed request leaves the issue queue"
assert eventually_updated(emma, f"Your request {big['name']} was closed")

# --- Receive stock
ian.api("receive_stock", item_code="A4-PAPER", qty=5, rate=650)

# --- Asset: issue -> acknowledge -> return with condition
emma_emp = me["employee"]["name"]
free = [a["name"] for a in ian.call("GET", "/api/resource/Asset?fields=" + urllib.request.quote('["name","custodian"]') + "&filters=" + urllib.request.quote('{"docstatus":1}') + "&limit_page_length=50") if not a["custodian"]]
asset = free[0]
assert asset.startswith("AST-"), asset
assert not emma.ok("POST", "/api/method/staffdock.api.issue_asset", {"asset": asset, "employee": emma_emp}), "employee must not issue assets"
move = ian.api("issue_asset", asset=asset, employee=emma_emp)
assert asset in emma.names("Asset"), "employee must see own asset"
assert asset not in olivia.names("Asset"), "others must not see asset"
assert any(t["name"] == move for t in emma.api("my_tasks")["assets_to_acknowledge"])
assert not olivia.ok("POST", WORKFLOW, {"doc": ian.get("Asset Movement", move), "action": "Acknowledge Receipt"}), "only receiver acknowledges"
assert eventually_updated(emma, "was assigned to you. Please confirm you received it")
assert emma.act("Asset Movement", move, "Acknowledge Receipt")["workflow_state"] == "Acknowledged"

ret = ian.api("receive_asset", asset=asset, condition="Minor Wear")
assert ian.get("Asset Movement", ret)["sd_return_condition"] == "Minor Wear"
assert not ian.get("Asset", asset)["custodian"], "returned asset must have no custodian"

# --- Leave: apply -> manager approves / rejects, withdraw, balance
DATE_FORMAT = {"dd-mm-yyyy": "%d-%m-%Y", "mm-dd-yyyy": "%m-%d-%Y", "yyyy-mm-dd": "%Y-%m-%d", "dd/mm/yyyy": "%d/%m/%Y", "mm/dd/yyyy": "%m/%d/%Y"}[
	emma.api("me")["date_format"]
]
import datetime

def leave_window(weeks_ahead=1):
	"""A Monday-Tuesday in a coming week; the test cancels or rejects what it books, so this stays free."""
	start = datetime.date.today() + datetime.timedelta(days=7 * weeks_ahead)
	start -= datetime.timedelta(days=start.weekday())
	return start.isoformat(), (start + datetime.timedelta(days=1)).isoformat()


def fmt(iso):
	"""Dates in notices use the site's format (dd-mm-yyyy on the demo site)."""
	return datetime.date.fromisoformat(iso).strftime(DATE_FORMAT)


def casual(session):
	return next(b for b in session.api("leave_summary")["balances"] if b["leave_type"] == "Casual Leave")

# Clear leave left by an earlier run that stopped half-way
for a in emma.api("leave_summary")["applications"]:
	if (a["description"] or "").startswith("e2e") and a["status"] in ("Open", "Approved"):
		if a["docstatus"] == 0:
			emma.api("withdraw_leave", name=a["name"])
		else:
			hana.call("POST", "/api/method/frappe.client.cancel", {"doctype": "Leave Application", "name": a["name"]})

before = casual(emma)
f, t = leave_window(1)
leave = emma.api("apply_leave", leave_type="Casual Leave", from_date=f, to_date=t, reason="e2e leave")
assert any(l["name"] == leave for l in max.api("my_tasks")["leaves_to_approve"]), "manager sees leave in tasks"
assert max.api("me")["is_approver"]
assert not emma.ok("POST", "/api/method/staffdock.api.decide_leave", {"name": leave, "approve": 1}), "no self-approval"
assert not olivia.ok("POST", "/api/method/staffdock.api.decide_leave", {"name": leave, "approve": 1}), "only the approver decides"
assert not olivia.ok("POST", "/api/method/staffdock.api.withdraw_leave", {"name": leave}), "only the employee withdraws"
assert max.api("decide_leave", name=leave, approve=1) == "Approved"
after = casual(emma)
assert after["remaining"] == before["remaining"] - 2 and after["taken"] == before["taken"] + 2, (before, after)
assert eventually_updated(max, "Emma Employee applied for Casual Leave")
assert eventually_updated(emma, f"Your Casual Leave from {fmt(f)} was approved")
assert not max.ok("POST", "/api/method/staffdock.api.decide_leave", {"name": leave, "approve": 0}), "decided leave stays decided"

f, t = leave_window(2)
gone = emma.api("apply_leave", leave_type="Casual Leave", from_date=f, to_date=t, reason="e2e withdraw")
emma.api("withdraw_leave", name=gone)
assert all(a["name"] != gone for a in emma.api("leave_summary")["applications"]), "withdrawn leave is gone"

no = emma.api("apply_leave", leave_type="Sick Leave", from_date=f, to_date=t, reason="e2e reject")
assert max.api("decide_leave", name=no, approve=0) == "Rejected"
assert eventually_updated(emma, f"Your Sick Leave from {fmt(f)} was rejected")

try:
	f3, _ = leave_window(3)
	emma.api("apply_leave", leave_type="Sick Leave", from_date=f3, to_date=(datetime.date.fromisoformat(f3) + datetime.timedelta(days=11)).isoformat(), reason="too long")
	raise AssertionError("leave beyond balance must be refused")
except urllib.error.HTTPError as err:
	assert "balance" in err.msg.lower(), err.msg

# HR cancels the approved leave (normal HR action): balance comes back and the dates free up for the next run
hana.call("POST", "/api/method/frappe.client.cancel", {"doctype": "Leave Application", "name": leave})
assert casual(emma)["remaining"] == before["remaining"], "cancelled leave returns to the balance"

# --- Attendance: check in/out toggles, server time only, own records only
time.sleep(11)  # past the double-click window of any earlier toggle (e.g. a previous run)
was_in = emma.api("attendance_today")["checked_in"]
expect = "OUT" if was_in else "IN"
assert emma.api("check_in_out", time="2026-01-01 08:00:00") == expect  # a client-sent time is ignored
today = emma.api("attendance_today")
assert today["last"].startswith(datetime.date.today().isoformat()) and today["checked_in"] != was_in, today
assert emma.api("check_in_out") == expect and emma.api("attendance_today")["checked_in"] != was_in, "double click is ignored"
assert emma.api("attendance_history")[0]["first_in"], "today shows in history"
time.sleep(11)
assert emma.api("check_in_out") == ("IN" if was_in else "OUT") and emma.api("attendance_today")["checked_in"] == was_in
assert not emma.ok(
	"POST", "/api/resource/Employee Checkin", {"employee": emma_emp, "log_type": "IN", "time": "2026-01-01 08:00:00"}
), "employees can't write their own check-in times"
emma.api("check_in_out", time="2026-01-01 08:00:00")  # a client-sent time is ignored
assert emma.api("attendance_today")["last"].startswith(datetime.date.today().isoformat()), "server time only"
emma.api("check_in_out")  # back to where we started
assert not olivia.ok("GET", "/api/resource/Employee Checkin?filters=" + urllib.request.quote(json.dumps([["employee", "=", emma_emp]])) + "&limit_page_length=1") or not olivia.call(
	"GET", "/api/resource/Employee Checkin?filters=" + urllib.request.quote(json.dumps([["employee", "=", emma_emp]]))
), "others can't read someone's check-ins"

# --- My profile: own contact fields only, photo from own upload
profile = emma.api("update_profile", cell_number="+1 555 0100", personal_email="emma.home@example.org", designation="CEO")
assert profile["cell_number"] == "+1 555 0100" and profile["personal_email"] == "emma.home@example.org"
assert profile["designation"] == "Software Developer", "only contact fields are editable"
assert not emma.ok("POST", "/api/method/staffdock.api.update_profile", {"personal_email": "not-an-email"}), "bad email refused"
assert not emma.ok("PUT", f"/api/resource/Employee/{emma_emp}", {"cell_number": "1"}), "no direct Employee writes"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
photo = emma.upload("emma.png", PNG)
assert not olivia.ok("POST", "/api/method/staffdock.api.set_profile_photo", {"file_url": photo}), "can't use someone else's upload"
emma.api("set_profile_photo", file_url=photo)
assert emma.api("my_profile")["image"] == photo and emma.api("me")["image"] == photo

# --- People: directory without personal fields, holidays, who's out today
team = olivia.api("people")
names = {p["employee_name"] for p in team["employees"]}
assert {"Emma Employee", "Max Manager", "Ian Inventory", "Olivia Other", "Hana HR"} <= names, names
assert all("cell_number" not in p and "personal_email" not in p for p in team["employees"]), "work details only"
assert team["holidays"] and all(h["description"] not in ("Saturday", "Sunday") for h in team["holidays"]), team["holidays"]
if datetime.date.today().weekday() < 5:
	today = datetime.date.today().isoformat()
	away = emma.api("apply_leave", leave_type="Casual Leave", from_date=today, to_date=today, reason="e2e out today")
	max.api("decide_leave", name=away, approve=1)
	out = olivia.api("people")["out_today"]
	assert any(o["employee_name"] == "Emma Employee" for o in out) and all("leave_type" not in o for o in out), out
	hana.call("POST", "/api/method/frappe.client.cancel", {"doctype": "Leave Application", "name": away})
	assert all(o["employee_name"] != "Emma Employee" for o in olivia.api("people")["out_today"])

# --- Announcements and policies
assert any(a["title"] == "Welcome to StaffDock" for a in emma.api("announcements"))
assert not emma.ok("POST", "/api/resource/Staff Announcement", {"title": "x", "message": "x"}), "staff can't post announcements"
bad = hana.call("POST", "/api/resource/Staff Announcement", {"title": "e2e html", "message": "<p>hi</p><script>alert(1)</script>"})
assert all("<script" not in a["message"] for a in emma.api("announcements", limit=20)), "announcement HTML is sanitized"
hana.call("DELETE", f"/api/resource/Staff Announcement/{bad['name']}")

conduct = next(p for p in emma.api("policies") if p["title"] == "Code of Conduct")
if conduct["acknowledged"]:  # a previous run acknowledged it: HR publishes a new version
	hana.call("PUT", f"/api/resource/Staff Policy/{conduct['name']}", {"version": str(int(conduct["version"]) + 1)})
assert any(p["name"] == conduct["name"] for p in emma.api("my_tasks")["policies_to_acknowledge"]), "policy is a to-do"
emma.api("acknowledge_policy", name=conduct["name"])
emma.api("acknowledge_policy", name=conduct["name"])  # twice is harmless
assert next(p for p in emma.api("policies") if p["name"] == conduct["name"])["acknowledged"]
assert all(p["name"] != conduct["name"] for p in emma.api("my_tasks")["policies_to_acknowledge"])
acks = hana.call("GET", "/api/resource/Staff Policy Acknowledgement?filters=" + urllib.request.quote(json.dumps([["policy", "=", conduct["name"]], ["employee", "=", emma_emp]])) + "&fields=" + urllib.request.quote('["version"]'))
assert len([a for a in acks if a["version"] == next(p for p in emma.api("policies") if p["name"] == conduct["name"])["version"]]) == 1, acks
version = next(p for p in emma.api("policies") if p["name"] == conduct["name"])["version"]
hana.call("PUT", f"/api/resource/Staff Policy/{conduct['name']}", {"version": str(int(version) + 1)})
assert any(p["name"] == conduct["name"] for p in emma.api("my_tasks")["policies_to_acknowledge"]), "new version asks again"
assert not emma.ok("POST", "/api/resource/Staff Policy Acknowledgement", {"policy": conduct["name"], "version": "99", "employee": emma_emp}), "acks only through the portal"

# --- Expenses: claim with receipt -> manager approves / rejects, withdraw, privacy
types = emma.api("my_expenses")["types"]
assert "Travel" in types, types
receipt = emma.upload("taxi-receipt.png", PNG, is_private=1)
day = datetime.date.today().isoformat()
lines = [{"expense_date": day, "expense_type": "Travel", "amount": 42.5, "description": "Taxi"}, {"expense_date": day, "expense_type": "Food", "amount": 17.5, "description": "Lunch"}]
claim = emma.api("submit_expense", lines=lines, remark="e2e claim", receipt_url=receipt)
pending = {c["name"]: c for c in max.api("expenses_to_approve")}
assert claim in pending and pending[claim]["total_claimed_amount"] == 60 and pending[claim]["receipts"], pending.get(claim)
assert any(c["name"] == claim for c in max.api("my_tasks")["expenses_to_approve"])
assert olivia.status(receipt)[0] in (403, 404), "others can't open the receipt"
assert max.status(receipt)[0] == 200, "approver can open the receipt"
assert not emma.ok("POST", "/api/method/staffdock.api.decide_expense", {"name": claim, "approve": 1}), "no self-approval"
assert not olivia.ok("POST", "/api/method/staffdock.api.decide_expense", {"name": claim, "approve": 1}), "only the approver decides"
assert not olivia.ok("POST", "/api/method/staffdock.api.withdraw_expense", {"name": claim}), "only the employee withdraws"
assert max.api("decide_expense", name=claim, approve=1) == "Approved"
mine = {c["name"]: c for c in emma.api("my_expenses")["claims"]}
assert mine[claim]["approval_status"] == "Approved" and mine[claim]["docstatus"] == 1 and mine[claim]["status"] == "Unpaid", mine[claim]
no = emma.api("submit_expense", lines=[lines[0]], remark="e2e reject")
assert max.api("decide_expense", name=no, approve=0) == "Rejected"
gone = emma.api("submit_expense", lines=[lines[1]], remark="e2e withdraw")
emma.api("withdraw_expense", name=gone)
assert gone not in {c["name"] for c in emma.api("my_expenses")["claims"]}
try:
	max.api("submit_expense", lines=[lines[0]])
	raise AssertionError("someone without a manager must be told to ask HR")
except urllib.error.HTTPError as err:
	assert "approver" in err.msg, err.msg

# --- My documents: files HR attaches to the employee record, private to that employee
letter = hana.upload("offer-letter.png", PNG, is_private=1, doctype="Employee", docname=emma_emp)
assert any(d["file_url"] == letter for d in emma.api("my_documents")), "employee sees HR's file"
assert emma.status(letter)[0] == 200, "employee can download it"
assert olivia.status(letter)[0] in (403, 404) and all(d["file_url"] != letter for d in olivia.api("my_documents"))
assert all(d["file_url"] != emma.api("my_profile")["image"] for d in emma.api("my_documents")), "profile photo isn't listed"
hana.call("DELETE", "/api/resource/File/" + next(d["name"] for d in emma.api("my_documents") if d["file_url"] == letter))

# --- Email notifications follow the StaffDock setting (an admin switches it)
admin = Session("Administrator", ADMIN_PW)
SETTINGS = "/api/resource/StaffDock Settings/StaffDock Settings"

def queued_for(user, reference):
	q = admin.call("GET", "/api/resource/Email Queue?fields=" + urllib.request.quote('["name"]') + "&filters=" + urllib.request.quote(json.dumps([["reference_name", "=", reference]])))
	return any(user in json.dumps(admin.get("Email Queue", row["name"])) for row in q)

def new_request(reason):
	r = emma.call("POST", "/api/resource/Material Request", {"schedule_date": "2026-12-31", "sd_reason": reason, "items": [{"item_code": "A4-PAPER", "qty": 1, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}]})
	emma.act("Material Request", r["name"], "Submit")
	return r["name"]

admin.call("PUT", SETTINGS, {"send_email_notifications": 1})
try:
	mailed = new_request("e2e email on")
	assert eventually(lambda: queued_for("max@example.com", mailed)), "manager is emailed when email is on"
finally:
	admin.call("PUT", SETTINGS, {"send_email_notifications": 0})
quiet = new_request("e2e email off")
time.sleep(5)
assert not queued_for("max@example.com", quiet), "no email when the setting is off"

# --- Feature switches: off features vanish from the portal and refuse their endpoints
admin.call("PUT", SETTINGS, {"feature_leave": 0, "feature_expenses": 0})
try:
	features = emma.api("me")["features"]
	assert not features["leave"] and not features["expenses"] and features["attendance"], features
	assert not emma.ok("POST", "/api/method/staffdock.api.apply_leave", {"leave_type": "Casual Leave", "from_date": "2026-12-01", "to_date": "2026-12-01", "reason": "x"})
	assert not emma.ok("POST", "/api/method/staffdock.api.my_expenses", {})
	tasks = max.api("my_tasks")
	assert tasks["leaves_to_approve"] == [] and tasks["expenses_to_approve"] == [], "home still works with features off"
finally:
	admin.call("PUT", SETTINGS, {"feature_leave": 1, "feature_expenses": 1})
assert emma.api("me")["features"]["leave"] and emma.api("leave_summary")["balances"], "switching back on restores it"

print(f"OK  request {name} (stock entry {entry}), rejected {rej['name']}, asset {asset} issued {move} returned {ret}, leave {leave}")
