#!/usr/bin/env bash
# Install the scheduled-refresh timer as a systemd *user* unit.
#
#   deploy/scheduler/install_scheduler.sh [--repo PATH] [--python PATH]
#
# Defaults: the repository this script lives in, and its .venv. The API and web
# app are not involved: the timer runs `run_pipeline scheduled-refresh` directly.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/../.." && pwd)"
python=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) repo="$2"; shift 2 ;;
    --python) python="$2"; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
python="${python:-$repo/.venv/bin/python}"

unit_dir="$HOME/.config/systemd/user"
env_dir="$HOME/.config/crawlernest"
mkdir -p "$unit_dir" "$env_dir" "$HOME/.crawlernest/scheduled_refresh"

env_file="$env_dir/scheduler.env"
if [ ! -f "$env_file" ]; then
  umask 077
  cat > "$env_file" <<EOF
CRAWLERNEST_REPO=$repo
CRAWLERNEST_PYTHON=$python
CRAWLERNEST_PG_HOST=localhost
CRAWLERNEST_PG_DATABASE=clawer
CRAWLERNEST_PG_USER=test
CRAWLERNEST_PG_PASSWORD=
EOF
  echo "wrote $env_file -- set CRAWLERNEST_PG_PASSWORD there"
fi

install -m 0644 "$here/crawlernest-scheduled-refresh.service" "$unit_dir/"
install -m 0644 "$here/crawlernest-scheduled-refresh.timer" "$unit_dir/"
systemctl --user daemon-reload
systemctl --user enable --now crawlernest-scheduled-refresh.timer
systemctl --user list-timers crawlernest-scheduled-refresh.timer --no-pager
