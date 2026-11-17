# StaffDock

[![CI](https://github.com/mesubash/staffdock/actions/workflows/ci.yml/badge.svg)](https://github.com/mesubash/staffdock/actions/workflows/ci.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**Open-source employee management system (EMS) for Frappe / ERPNext.**

StaffDock gives every employee one simple portal for everyday work: attendance, leave, expenses, item
requests, company assets, the people directory and company policies. Managers approve from the same place.
HR and admins keep the full ERPNext / Frappe HR desk behind it.

ERPNext is powerful, but its desk is too much for someone who just wants to apply for leave. StaffDock keeps
the data in ERPNext and Frappe HR, and puts a small, role-aware portal in front of it.

## Features

**For employees**
- **Home**: check in/out, what's waiting on you, company announcements and recent updates.
- **Attendance**: check in and out (server time only, double clicks ignored), hours today and the last 30 days.
- **Leave**: balances, apply (including half days), withdraw while pending.
- **Expenses**: claim several expenses at once with a private receipt; follow them to paid.
- **Requests and assets**: request items from stores, confirm what you received, see company property you hold.
- **People**: directory with search, who's out today (the leave type stays private), upcoming holidays.
- **Policies**: read and acknowledge company policies; a new version asks again.
- **My profile**: job details and manager, update your contact and emergency details and photo, download
  documents HR shares with you.

**For managers**
- **Approvals**: leave, expenses and item requests from your team in one list, with receipts and history.

**For inventory staff**
- Review and issue requests, issue company assets and receive them back with their condition, stock levels,
  receive stock, close requests that can't be fulfilled.

**For HR and admins**
- Everything stays in ERPNext and Frappe HR: allocations, holidays, payroll, accounting and reports work as usual.
- Post announcements and policies in desk and see who acknowledged.
- One settings page for branding, an optional company email-domain lock, email notifications and feature switches.

**Throughout**
- Only the buttons you can use: actions come from the workflow, so nobody sees options they can't take.
- Row-level access: employees see their own records, managers their team's.
- A history on every request, in-app notifications and optional email.
- Light and dark mode, phone friendly, keyboard accessible.

## How it works

```
Staff portal (/staff)          React + Vite, one page app served by Frappe
        │  calls
staffdock.api                  thin, permission-checked endpoints
        │  uses
ERPNext + Frappe HR            Material Request, Stock Entry, Asset, Asset Movement,
                               Leave Application, Employee Checkin, Expense Claim, Employee
```

StaffDock adds custom fields, roles, workflows and notifications through code (`staffdock/setup.py`, applied on
every `bench migrate`) and never modifies Frappe, ERPNext or Frappe HR. Stock, asset, leave and expense records
stay in ERPNext's own ledgers.

## Roles

| Role | Uses | Gets |
|---|---|---|
| Employee | Portal only (no desk) | Their own attendance, leave, expenses, requests, assets, profile |
| Manager (has reportees, or set as leave/expense approver) | Portal | + Approvals for their team |
| Inventory | Portal | + Inventory: requests to review and issue, assets, stock |
| HR (HR Manager / HR User) | Portal + desk (Frappe HR) | HR records, announcements, policies |
| Admin (System Manager) | Portal + desk (ERPNext + Frappe HR) | Everything |

## Install

Requires Frappe v16, ERPNext v16 and Frappe HR v16 on an existing bench.

```sh
bench get-app https://github.com/mesubash/staffdock
bench --site <site> install-app staffdock
```

`bench get-app` builds the portal during the normal asset build (it uses the Node and yarn every bench already
has). Staff then use `https://<site>/staff`.

## Configure

Desk → search **StaffDock Settings**:

| Setting | Effect |
|---|---|
| App Name, Logo | Sign-in page, portal header, browser tab |
| Company Email Domain | Only accounts on this email domain can be created |
| Default Store | Warehouse used for requests, issues and receipts |
| Send Email Notifications | Also email every portal notice (needs a default outgoing Email Account) |
| Features | Switch off Requests/Assets/Inventory, Attendance, Leave, Expenses, People or Announcements/Policies |

Leave and expenses go to the employee's reporting manager unless HR sets a different approver on the employee.

### Single sign-on

StaffDock has no login code of its own; it uses Frappe's sign-in page. To let staff sign in with Google,
Microsoft or your own identity provider, add a **Social Login Key** in desk (any standard OAuth 2.0 / OpenID
Connect provider) and the button appears on the sign-in page.

## Development

The Docker setup includes MariaDB, Redis, a Frappe bench container and Mailpit (catches outgoing mail).

```sh
docker compose -f compose.dev.yml up -d
docker compose -f compose.dev.yml exec frappe bash /workspace/scripts/dev-setup.sh
docker compose -f compose.dev.yml exec -w /workspace/development/frappe-bench frappe bench start
```

`dev-setup.sh` creates the bench, links this checkout into it, creates the `staffdock.localhost` site and
seeds a demo company (Acme Corp) with one user per role: `emma@example.com` (employee), `max@` (her manager),
`ian@` (inventory), `olivia@` (another team) and `hana@` (HR). Passwords are written to
`development/site-credentials.txt`.

- Portal: http://staffdock.localhost:8000/staff · Desk: http://staffdock.localhost:8000/desk
- Mail: http://localhost:8025
- Portal with hot reload: `yarn install && yarn dev`, then http://staffdock.localhost:8080/staff
  (set `ignore_csrf: 1` in the site config)

### Tests

`scripts/e2e_check.py` drives every role through attendance, leave, expenses, requests, assets, people,
policies, notifications and the access rules against the running site. CI runs it on a fresh bench for every
push.

```sh
python3 scripts/e2e_check.py
```

## Project layout

```
staffdock/            Frappe app: API, permissions, workflows, settings, doctypes, setup
portal/               Staff portal (React + Vite), built into staffdock/public/portal
scripts/              dev-setup.sh and the end-to-end check
compose.dev.yml       Development containers
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and, for security issues,
[SECURITY.md](SECURITY.md).

## License

GPL-3.0. See [LICENSE](LICENSE).
