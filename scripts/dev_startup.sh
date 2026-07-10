#!/bin/sh
set -e

# Change to project root directory
cd "$(dirname "$0")/.."

# Activate venv if it exists, otherwise run directly
if [ -f .venv/bin/activate ]; then
    . .venv/bin/activate
fi

python3 manage.py runserver
