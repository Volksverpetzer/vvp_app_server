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

_signaled=""
_shutting_down=""
sleep_pid=""
shutdown() {
    # Guard so a trapped signal + the supervision fallthrough don't run twice.
    [ -n "$_shutting_down" ] && return
    _shutting_down=1
    trap - TERM INT
    kill -TERM "$gunicorn_pid" "$qcluster_pid" 2>/dev/null || true
    # Also reap a pending supervision sleep so it doesn't delay exit.
    [ -n "$sleep_pid" ] && kill "$sleep_pid" 2>/dev/null || true
}
on_signal() {
    _signaled=1
    shutdown
}
trap on_signal TERM INT

# Supervise BOTH children: leave the loop as soon as either exits (or a
# trapped signal initiated shutdown). POSIX sh has no `wait -n`, so poll
# with an interruptible backgrounded sleep (a plain `sleep 5` would delay
# signal delivery until it finishes).
while kill -0 "$gunicorn_pid" 2>/dev/null && kill -0 "$qcluster_pid" 2>/dev/null; do
    sleep 5 &
    sleep_pid=$!
    wait "$sleep_pid" || true
done
sleep_pid=""

# Record whether the worker died on its own BEFORE we initiate teardown —
# afterwards it is dead either way.
qcluster_died=""
kill -0 "$qcluster_pid" 2>/dev/null || qcluster_died=1

shutdown

# Collect Gunicorn's real exit status (the shell retains it after death).
# The || guard keeps `set -e` from bailing before full teardown.
gunicorn_status=0
wait "$gunicorn_pid" || gunicorn_status=$?
# Wait for ALL remaining children before PID 1 exits — Gunicorn may still be
# draining connections (up to --timeout). Exiting early would let Docker
# force-kill it mid-shutdown.
# Note: a bare `wait` (no operands) always returns 0 per POSIX, regardless of
# the children's exit statuses, so it cannot trip `set -e`. Do not refactor
# this to `wait "$pid"` — an operand form returns that child's status and
# WOULD abort under `set -e` before the exit lines below.
wait

# Exit status: propagate Gunicorn's. If the qcluster worker died on its own
# (not as part of a signal-initiated shutdown), force non-zero even when
# Gunicorn shut down cleanly, so the orchestrator restarts the container
# instead of serving HTTP with no background worker.
if [ -n "$qcluster_died" ] && [ -z "$_signaled" ] && [ "$gunicorn_status" -eq 0 ]; then
    echo "startup.sh: qcluster worker exited unexpectedly; restarting container" >&2
    exit 1
fi
exit "$gunicorn_status"
