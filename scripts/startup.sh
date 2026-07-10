#!/bin/sh
set -e

# Change to project root directory
cd "$(dirname "$0")/.."

python manage.py migrate
python manage.py createcachetable cache_table

# Run the Django-Q worker and Gunicorn as sibling child processes and
# forward termination signals to both. We deliberately do NOT `exec`
# Gunicorn: that would make it PID 1 and leave the qcluster worker to be
# force-killed (not gracefully stopped) when the container shuts down.
python manage.py qcluster &
qcluster_pid=$!

gunicorn --bind=0.0.0.0:8080 --timeout 600 vvp_app_server.wsgi \
    --access-logfile '-' --error-logfile '-' &
gunicorn_pid=$!

_shutting_down=""
shutdown() {
    # Guard so a trapped signal + the post-wait call don't run this twice.
    [ -n "$_shutting_down" ] && return
    _shutting_down=1
    trap - TERM INT
    kill -TERM "$gunicorn_pid" "$qcluster_pid" 2>/dev/null || true
}
trap shutdown TERM INT

# Block on Gunicorn. A trapped SIGTERM/SIGINT interrupts this wait and runs
# shutdown(); if Gunicorn exits on its own we fall through and tear down the
# worker too. Capture its status (|| guard keeps `set -e` from bailing before
# teardown) so a crash still propagates and the container can restart.
gunicorn_status=0
wait "$gunicorn_pid" || gunicorn_status=$?
shutdown
# Wait for BOTH children to fully exit before PID 1 does — Gunicorn may still
# be draining connections (up to --timeout). Exiting here would let Docker
# force-kill it mid-shutdown.
# Note: a bare `wait` (no operands) always returns 0 per POSIX, regardless of
# the children's exit statuses, so it cannot trip `set -e`. Do not refactor
# this to `wait "$pid"` — an operand form returns that child's status and
# WOULD abort under `set -e` before the exit line below.
wait
exit "$gunicorn_status"
