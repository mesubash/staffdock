# StaffDock

**Open-source employee management system (EMS) for Frappe / ERPNext.**
A simple, role-based staff portal for requests, approvals, assets and inventory, on top of ERPNext and Frappe HR.

Employees get one clean place for everyday work; HR and admins keep the full ERPNext desk.

## Features

- **Staff portal** (`/staff`): see what's waiting on you, nothing else. Sign-in uses Frappe's own login
  (password reset, 2FA, and "Sign in with …" through any OAuth/OIDC provider via Social Login Keys).
- **Item requests**: employee → manager → inventory → issue from store → employee confirms receipt.
- **Attendance**: check in / check out from the portal (server time only, double clicks ignored),
  hours today and the last 30 days. Stored as Frappe HR Employee Checkins; optional location when HR enables it.
- **Leave**: balances, apply (incl. half day), manager approves or rejects, withdraw while pending.
  Built on Frappe HR Leave Application, so allocations, holidays and HR reports work as usual.
- **Assets**: issue company property to an employee, they confirm receipt, receive it back with its condition.
- **Inventory**: review and issue requests, stock levels, receive stock.
- **History** on every request: who did what, when.
- **Only the buttons you can use**: actions come from the workflow, so people never see options they can't take.
- **Row-level access**: employees see only their own records, managers their team's.
- **Company domain lock**: only accounts on your email domain can exist (optional).

Built on standard ERPNext doctypes (Material Request, Stock Entry, Asset, Asset Movement) and Frappe workflows,
so stock and asset history stay in ERPNext's ledgers.

## Roles

| Role | Uses | Sees |
|---|---|---|
| Employee | Portal only (no desk) | Own requests and assets; confirm receipts |
| Manager (anyone with reportees or set as leave approver) | Portal | + team approvals (requests and leave) |
| Inventory | Portal | + review/issue requests, issue/receive assets, stock levels, receive stock |
| HR (HR Manager / HR User) | Portal + desk (Frappe HR) | HR records and settings |
| Admin (System Manager) | Portal + desk (ERPNext + Frappe HR) | Everything |

## Configure

**StaffDock Settings** (desk → search "StaffDock Settings"):

| Setting | Effect |
|---|---|
| App Name, Logo | Sign-in page, portal header, browser tab |
| Company Email Domain | Only accounts on this email domain can be created |
| Default Store | Warehouse used for requests, issues and receipts |

## Single sign-on

StaffDock has no login code of its own. To let staff sign in with Google, Microsoft or your own
identity provider, add a **Social Login Key** in desk (any standard OAuth 2.0 / OpenID Connect provider);
the button appears on the sign-in page.

## Install

Requires Frappe v16, ERPNext v16 and Frappe HR v16.

```sh
bench get-app https://github.com/mesubash/staffdock
bench --site <site> install-app staffdock
```

`bench get-app` builds the staff portal as part of the normal asset build (it needs Node and yarn,
which every Frappe bench already has). The portal is at `https://<site>/staff`.

## Development

Docker dev environment (MariaDB 11.8, Redis, frappe/bench):

```sh
docker compose -f compose.dev.yml up -d
docker compose -f compose.dev.yml exec frappe bash
```

First time, inside the container (from `/workspace/development`):

```sh
bench init --skip-redis-config-generation --frappe-branch version-16 --python python3.14 frappe-bench
cd frappe-bench
bench set-config -g db_host mariadb
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench get-app --branch version-16 erpnext
bench get-app --branch version-16 hrms
ln -s ../../.. apps/staffdock && echo staffdock >> sites/apps.txt
uv pip install -e apps/staffdock --python env/bin/python
bench new-site staffdock.localhost --db-root-password 123 --admin-password <choose> --mariadb-user-host-login-scope=%
bench --site staffdock.localhost install-app erpnext hrms staffdock
bench --site staffdock.localhost set-config developer_mode 1
bench use staffdock.localhost
bench --site staffdock.localhost execute staffdock.dev_seed.run --kwargs '{"password": "<demo password>"}'
bench start
```

The seed runs the setup wizard (Acme Corp), adds a holiday list and leave allocations, and creates one demo user per role:
`emma@example.com` (employee), `max@` (her manager), `ian@` (inventory), `olivia@` (another team), `hana@` (HR).

Portal: http://staffdock.localhost:8000/staff · Desk: http://staffdock.localhost:8000/desk

Portal with hot reload: `yarn install && yarn dev` (repo root), open http://staffdock.localhost:8080/staff
(set `ignore_csrf: 1` in the dev site config).

### End-to-end check

Runs every role through the full request and asset flow, plus the access rules:

```sh
python3 scripts/e2e_check.py   # reads test_password from development/site-credentials.txt
```

## Layout

```
staffdock/            Frappe app (hooks, API, permissions, workflows, settings)
portal/               Staff portal (React + Vite), built into staffdock/public/portal
scripts/e2e_check.py  End-to-end check
compose.dev.yml       Dev containers
```

Configuration (custom fields, roles, permissions, workflows, notifications) lives in `staffdock/setup.py`
and is applied on every `bench migrate`. Upstream Frappe / ERPNext / HRMS code is never modified.

## License

GPL-3.0. See [LICENSE](LICENSE).
