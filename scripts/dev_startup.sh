#!/bin/sh
# Change to project root directory
cd "$(dirname "$0")/.."

# activate venv and run development server
source .venv/bin/activate
python3 manage.py runserver
