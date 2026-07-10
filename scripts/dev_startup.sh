#!/bin/sh
set -e

# Change to project root directory
cd "$(dirname "$0")/.."

# Activate the virtualenv if one exists (this repo uses venv/, but also
# support the common .venv/ layout); otherwise fall back to system python.
if [ -f venv/bin/activate ]; then
    . venv/bin/activate
elif [ -f .venv/bin/activate ]; then
    . .venv/bin/activate
fi

python3 manage.py runserver
