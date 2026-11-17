app_name = "staffdock"
app_title = "StaffDock"
app_publisher = "Subash Singh Dhami"
app_description = "Open-source employee management system for Frappe/ERPNext"
app_email = "subashdhamee@gmail.com"
app_license = "agpl-3.0"

# Staff portal (React app in /portal, built into public/portal)
website_route_rules = [{"from_route": "/staff/<path:app_path>", "to_route": "staff"}]
before_request = ["staffdock.portal.redirect_staff_to_portal"]

extend_bootinfo = "staffdock.boot.extend_bootinfo"

after_install = "staffdock.setup.after_migrate"
after_migrate = "staffdock.setup.after_migrate"

permission_query_conditions = {
	"Material Request": "staffdock.permissions.material_request_query",
	"Asset": "staffdock.permissions.asset_query",
	"Asset Movement": "staffdock.permissions.asset_movement_query",
}

has_permission = {
	"Material Request": "staffdock.permissions.material_request_has_permission",
	"Asset": "staffdock.permissions.asset_has_permission",
	"Asset Movement": "staffdock.permissions.asset_movement_has_permission",
}

doc_events = {
	"User": {"validate": "staffdock.users.user_validate", "on_update": "staffdock.events.user_on_update"},
	"Employee": {"validate": "staffdock.events.employee_validate"},
	"Material Request": {
		"validate": "staffdock.events.material_request_validate",
		"before_submit": "staffdock.events.require_workflow_submit",
	},
	"Asset Movement": {
		"before_submit": "staffdock.events.require_workflow_submit",
		"on_submit": "staffdock.events.asset_movement_on_submit",
	},
}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "staffdock",
# 		"logo": "/assets/staffdock/logo.png",
# 		"title": "StaffDock",
# 		"route": "/staffdock",
# 		"has_permission": "staffdock.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `staffdock/dock/staffdock/staffdock.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/staffdock/css/staffdock.css"
# app_include_js = "/assets/staffdock/js/staffdock.js"

# include js, css files in header of web template
# web_include_css = "/assets/staffdock/css/staffdock.css"
# web_include_js = "/assets/staffdock/js/staffdock.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "staffdock/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "staffdock/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "staffdock.utils.jinja_methods",
# 	"filters": "staffdock.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "staffdock.install.before_install"
# after_install = "staffdock.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "staffdock.uninstall.before_uninstall"
# after_uninstall = "staffdock.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "staffdock.utils.before_app_install"
# after_app_install = "staffdock.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "staffdock.utils.before_app_uninstall"
# after_app_uninstall = "staffdock.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "staffdock.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "staffdock.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "staffdock.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["staffdock.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"staffdock.tasks.all"
# 	],
# 	"daily": [
# 		"staffdock.tasks.daily"
# 	],
# 	"hourly": [
# 		"staffdock.tasks.hourly"
# 	],
# 	"weekly": [
# 		"staffdock.tasks.weekly"
# 	],
# 	"monthly": [
# 		"staffdock.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "staffdock.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "staffdock.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "staffdock.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "staffdock.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["staffdock.utils.before_request"]
# after_request = ["staffdock.utils.after_request"]

# Job Events
# ----------
# before_job = ["staffdock.utils.before_job"]
# after_job = ["staffdock.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"staffdock.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
