"""End-to-end check of the inventory MVP against a running dev site.

python3 scripts/e2e_check.py   (reads test password from development/site-credentials.txt)

Creates new records each run. Dev only.
"""

import http.cookiejar
import json
import pathlib
import re
import urllib.error
import urllib.request

BASE = "http://staffdock.localhost:8000"
CREDS = dict(
	line.split("=", 1) for line in (pathlib.Path(__file__).parent.parent / "development/site-credentials.txt").read_text().split()
)
PW = CREDS["test_password"]


class Session:
	def __init__(self, user):
		self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
		self.csrf = ""
		self.call("POST", "/api/method/login", {"usr": user, "pwd": PW})
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

bypass = emma.call(
	"POST",
	"/api/resource/Material Request",
	{"schedule_date": "2026-12-31", "items": [{"item_code": "A4-PAPER", "qty": 1, "warehouse": "Stores - AC", "schedule_date": "2026-12-31"}]},
)
assert not emma.ok("POST", "/api/method/frappe.client.submit", {"doc": emma.get("Material Request", bypass["name"])}), "must not skip workflow"

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

# --- Receive stock
ian.api("receive_stock", item_code="A4-PAPER", qty=5, rate=650)

# --- Asset: issue -> acknowledge -> return with condition
emma_emp = me["employee"]["name"]
free = [a["name"] for a in ian.call("GET", "/api/resource/Asset?fields=" + urllib.request.quote('["name","custodian"]') + "&filters=" + urllib.request.quote('{"docstatus":1}') + "&limit_page_length=50") if not a["custodian"]]
asset = free[0]
assert not emma.ok("POST", "/api/method/staffdock.api.issue_asset", {"asset": asset, "employee": emma_emp}), "employee must not issue assets"
move = ian.api("issue_asset", asset=asset, employee=emma_emp)
assert asset in emma.names("Asset"), "employee must see own asset"
assert asset not in olivia.names("Asset"), "others must not see asset"
assert any(t["name"] == move for t in emma.api("my_tasks")["assets_to_acknowledge"])
assert not olivia.ok("POST", WORKFLOW, {"doc": ian.get("Asset Movement", move), "action": "Acknowledge Receipt"}), "only receiver acknowledges"
assert emma.act("Asset Movement", move, "Acknowledge Receipt")["workflow_state"] == "Acknowledged"

ret = ian.api("receive_asset", asset=asset, condition="Minor Wear")
assert ian.get("Asset Movement", ret)["sd_return_condition"] == "Minor Wear"
assert not ian.get("Asset", asset)["custodian"], "returned asset must have no custodian"

print(f"OK  request {name} (stock entry {entry}), rejected {rej['name']}, asset {asset} issued {move} returned {ret}")
