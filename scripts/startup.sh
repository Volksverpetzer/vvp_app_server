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
# worker too. Either way both processes stop before the container exits.
wait "$gunicorn_pid" || true
shutdown
wait "$qcluster_pid" 2>/dev/null || true
