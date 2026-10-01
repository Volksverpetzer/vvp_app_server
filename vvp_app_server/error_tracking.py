"""Optional error tracking against a self-hosted GlitchTip (Sentry-compatible).

Inactive unless ``GLITCHTIP_DSN`` is set, so dev, tests and deployments
without a GlitchTip instance are unaffected.
"""

import json
import re

# Expo push tokens identify a device, so they must not leave the server.
_EXPO_TOKEN_RE = re.compile(r"Expo(?:nent)?PushToken\[[^\]]*\]")


def scrub_event(event, hint):
    """Redact Expo push tokens anywhere in an outgoing error event."""
    scrubbed = _EXPO_TOKEN_RE.sub("[expo-token]", json.dumps(event, default=str))
    return json.loads(scrubbed)


def init_error_tracking(dsn: str | None, release: str) -> bool:
    """Initialise the SDK when a DSN is configured. Returns whether it is on."""
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(
        dsn=dsn,
        release=release,
        send_default_pii=False,
        traces_sample_rate=0,
        before_send=scrub_event,
    )
    return True
