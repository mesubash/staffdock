#!/usr/bin/env bash
# Set up a StaffDock development bench and demo site. Safe to re-run; finished steps are skipped.
#
# Inside the dev container:   bash /workspace/scripts/dev-setup.sh
# Anywhere else (e.g. CI):    DB_HOST=127.0.0.1 REDIS_CACHE=redis://127.0.0.1:6379 ... bash scripts/dev-setup.sh
#
# Writes the generated passwords to $BENCH_PARENT/site-credentials.txt (read by scripts/e2e_check.py).
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCH_PARENT="${BENCH_PARENT:-$APP_DIR/development}"
BENCH_DIR="$BENCH_PARENT/frappe-bench"
SITE="${SITE:-staffdock.localhost}"
FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}"
PYTHON="${PYTHON:-python3.14}"
DB_HOST="${DB_HOST:-mariadb}"
DB_ROOT_PASSWORD="${DB_ROOT_PASSWORD:-123}"
REDIS_CACHE="${REDIS_CACHE:-redis://redis-cache:6379}"
REDIS_QUEUE="${REDIS_QUEUE:-redis://redis-queue:6379}"
MAIL_HOST="${MAIL_HOST:-mailpit}"
CREDS="$BENCH_PARENT/site-credentials.txt"

random_password() { head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 18; }

mkdir -p "$BENCH_PARENT"
if [[ -f "$CREDS" ]]; then
	ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(sed -n 's/^password=//p' "$CREDS")}"
	TEST_PASSWORD="${TEST_PASSWORD:-$(sed -n 's/^test_password=//p' "$CREDS")}"
fi
ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(random_password)}"
TEST_PASSWORD="${TEST_PASSWORD:-$(random_password)}"
(umask 077 && printf 'site=%s\npassword=%s\ntest_password=%s\n' "$SITE" "$ADMIN_PASSWORD" "$TEST_PASSWORD" > "$CREDS")

if [[ ! -d "$BENCH_DIR" ]]; then
	(cd "$BENCH_PARENT" && bench init --skip-redis-config-generation --frappe-branch "$FRAPPE_BRANCH" --python "$PYTHON" frappe-bench)
fi
cd "$BENCH_DIR"
bench set-config -g db_host "$DB_HOST"
bench set-config -g redis_cache "$REDIS_CACHE"
bench set-config -g redis_queue "$REDIS_QUEUE"
bench set-config -g redis_socketio "$REDIS_QUEUE"

[[ -d apps/erpnext ]] || bench get-app --branch "$FRAPPE_BRANCH" erpnext
[[ -d apps/hrms ]] || bench get-app --branch "$FRAPPE_BRANCH" hrms

# Link this checkout into the bench so code changes show up live
if [[ ! -e apps/staffdock ]]; then
	ln -s "$APP_DIR" apps/staffdock
	# apps.txt has no trailing newline; add the app as its own line and drop blank lines
	if ! grep -qx staffdock sites/apps.txt; then
		printf '\nstaffdock\n' >> sites/apps.txt
		sed -i.bak '/^$/d' sites/apps.txt && rm -f sites/apps.txt.bak
	fi
	if command -v uv > /dev/null; then
		uv pip install --quiet -e apps/staffdock --python env/bin/python
	else
		env/bin/python -m pip install --quiet -e apps/staffdock
	fi
fi
bench build --app staffdock

if [[ ! -d "sites/$SITE" ]]; then
	bench new-site "$SITE" --db-root-password "$DB_ROOT_PASSWORD" --admin-password "$ADMIN_PASSWORD" \
		--mariadb-user-host-login-scope=%
	bench --site "$SITE" install-app erpnext hrms staffdock
fi
bench --site "$SITE" set-config developer_mode 1
bench --site "$SITE" set-config dev_mail_host "$MAIL_HOST"
bench use "$SITE"
bench --site "$SITE" execute staffdock.dev_seed.run --kwargs "{\"password\": \"$TEST_PASSWORD\"}"

cat <<DONE

StaffDock is ready. Start it with:  cd $BENCH_DIR && bench start
  Portal  http://$SITE:8000/staff   (demo users emma/max/ian/olivia/hana @example.com)
  Desk    http://$SITE:8000/desk    (Administrator)
  Passwords are in $CREDS
DONE
