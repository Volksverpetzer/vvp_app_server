#!/bin/sh
set -eu
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# .env is not a shell script: values may contain unquoted shell
# metacharacters (e.g. & in SECRET_KEY), so sourcing it can fail with a
# parse error. Extract only the variables we need, stripping optional
# surrounding quotes. Variables already set in the environment win.
env_var() {
    [ -f "$ENV_FILE" ] || return 0
    val=$(grep "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2-)
    case $val in
        \"*\") val=${val#?}; val=${val%?} ;;
        \'*\') val=${val#?}; val=${val%?} ;;
    esac
    printf '%s' "$val"
}

SCALEWAY_API_KEY=${SCALEWAY_API_KEY:-$(env_var SCALEWAY_API_KEY)}
SCALEWAY_INSTANCE_ID=${SCALEWAY_INSTANCE_ID:-$(env_var SCALEWAY_INSTANCE_ID)}
SCALEWAY_REGION=${SCALEWAY_REGION:-$(env_var SCALEWAY_REGION)}
export SCALEWAY_API_KEY SCALEWAY_INSTANCE_ID SCALEWAY_REGION

exec sh "$SCRIPT_DIR/add_ip_to_scaleway_allowlist.sh"
