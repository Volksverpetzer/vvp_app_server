#!/bin/sh
set -eu

: "${SCALEWAY_INSTANCE_ID:?SCALEWAY_INSTANCE_ID is required}"
: "${SCALEWAY_REGION:?SCALEWAY_REGION is required}"
: "${SCALEWAY_API_KEY:?SCALEWAY_API_KEY is required}"

for dep in curl python3; do
    if ! command -v "$dep" >/dev/null 2>&1; then
        echo "Error: $dep is required but not installed" >&2
        exit 1
    fi
done

echo "Detecting current public IPv4..."
PUBLIC_IP=$(curl -fsS -4 --connect-timeout 10 --max-time 30 https://ifconfig.me | tr -d '[:space:]')
echo "$PUBLIC_IP" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}$' || {
    echo "Error: Unable to determine public IPv4 (got: '$PUBLIC_IP')" >&2
    exit 1
}
CIDR="$PUBLIC_IP/32"

ACL_ENDPOINT="https://api.scaleway.com/rdb/v1/regions/$SCALEWAY_REGION/instances/$SCALEWAY_INSTANCE_ID/acls"

echo "Adding $CIDR to the allow list..."
PAYLOAD=$(python3 - "$CIDR" <<'PY'
import json
import sys

cidr = sys.argv[1]
print(json.dumps({
    "rules": [
        {
            "ip": cidr,
            "description": "Added via script"
        }
    ]
}))
PY
)
API_RESPONSE=$(curl -sS --connect-timeout 10 --max-time 30 -w "\n%{http_code}" -X POST \
    -H "Content-Type: application/json" \
    -H "X-Auth-Token: $SCALEWAY_API_KEY" \
    -d "$PAYLOAD" \
    "$ACL_ENDPOINT")

HTTP_STATUS=$(printf '%s' "$API_RESPONSE" | tail -n1)
BODY=$(printf '%s' "$API_RESPONSE" | sed '$d')

if [ "$HTTP_STATUS" -ge 400 ]; then
    echo "Scaleway API error ($HTTP_STATUS): $BODY" >&2
    exit 1
fi

echo "Successfully added $CIDR to the allow list for instance $SCALEWAY_INSTANCE_ID in $SCALEWAY_REGION."
