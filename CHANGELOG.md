# Changelog

All notable changes to StaffDock. The format follows [Keep a Changelog](https://keepachangelog.com/)
and the project uses [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-11-17

First public release, licensed under AGPL-3.0. Requires Frappe v16, ERPNext v16 and Frappe HR v16.

### Added
- Staff portal at `/staff`, served by Frappe, using Frappe's own sign-in page.
- Attendance: check in/out with server time, hours today and the last 30 days.
- Leave: balances, apply, withdraw; manager approval and rejection.
- Expenses: claims with private receipts; manager approval; finance pays in desk.
- Item requests: manager and inventory approval, issue from stores, receipt confirmation, close
  requests that can't be fulfilled, history.
- Assets: issue to employees, acknowledgement, return with condition.
- Inventory: review and issue requests, stock levels, receive stock.
- People: directory, who's out today, upcoming holidays.
- Announcements and policies with versioned acknowledgements.
- My profile: contact and emergency details, photo, documents shared by HR.
- In-app notifications, optional email notifications.
- StaffDock Settings: branding, email-domain lock, default store, email switch, feature switches.
- Row-level access for employees and managers; staff have no desk access.
- Light and dark mode, phone layout, keyboard access.
- Docker development setup, demo seed and an end-to-end check covering every role.
