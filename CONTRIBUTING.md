# Contributing to StaffDock

Thanks for helping. Bug reports, ideas and pull requests are all welcome.

## Getting started

Follow [Development](README.md#development) in the README: three commands give you a running bench,
a demo company and one user per role.

## Ground rules

- **Never change Frappe, ERPNext or Frappe HR code.** Use hooks, custom fields, workflows and the
  setup code in `staffdock/setup.py` (applied on every `bench migrate`).
- **Keep the portal simple.** Staff should only see what they need and only the buttons they can use.
  Anything rare belongs in desk.
- **Check permissions on the server.** Every `staffdock.api` endpoint must decide who may do what;
  never rely on the portal hiding a button.
- **Reuse ERPNext / Frappe HR records** (Leave Application, Expense Claim, Material Request …) instead of
  adding parallel doctypes.
- **Keep the code generic.** No company-specific names, domains or data; those belong in StaffDock Settings.

## Making a change

1. Fork, then create a branch: `feature/<short-name>` or `fix/<short-name>`.
2. Make the change and extend `scripts/e2e_check.py` so the behaviour is covered, including who must
   *not* be able to do it.
3. Run the checks:
   ```sh
   python3 scripts/e2e_check.py      # against your dev site
   uvx ruff check staffdock scripts  # Python lint
   uvx ruff format --check staffdock scripts
   yarn build                        # portal type check and build
   ```
4. Open a pull request describing the problem, the change and how you tested it.

## Commit messages

Short imperative subject (`Add expense receipts to approvals`), blank line, then why the change was
needed if it isn't obvious.

## Reporting bugs

Open an issue with the steps to reproduce, what you expected and what happened, plus your Frappe,
ERPNext and Frappe HR versions. For security problems see [SECURITY.md](SECURITY.md) instead.
