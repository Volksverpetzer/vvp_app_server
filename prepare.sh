#!/bin/bash

echo "Prepare Version: $1"
sed -i -e "s/__version__\s*=\s*\".*\"/__version__ = \"$1\"/g" vvp_app_server/__init__.py
