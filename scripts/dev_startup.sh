#!/bin/sh
set -e

# Change to project root directory
cd "$(dirname "$0")/.."

# Activate the virtualenv if one exists — .venv/ per the README setup,
# venv/ as a fallback layout; otherwise fall back to system python.
if [ -f .venv/bin/activate ]; then
    . .venv/bin/activate
elif [ -f venv/bin/activate ]; then
    . venv/bin/activate
fi

python3 manage.py runserver
