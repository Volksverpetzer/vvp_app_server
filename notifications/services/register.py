import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from exponent_server_sdk import PushClient  # type: ignore[reportMissingTypeStubs]
from notifications.models import NotificationDevice

logger = logging.getLogger(__name__)


@csrf_exempt
def register(request: HttpRequest) -> JsonResponse:
    """Register a device for notifications or change settings.

    Args:
        request (django request): django POST request with a json body that
            contains two keys: "expo_token" and "settings". "settings" is a
            dictionary with the keys "new_post", "new_fact_check" and the
            optional "new_pruefpunkt". Each of these is a dictionary with one
            key: "value". Optional: "os" (stored as platform) and "version"
            (the native build number, stored as app_build).

    Returns:
        JsonResponse:
            - 200 on success
            - 400 on a malformed request (invalid JSON, missing "expo_token"/
              "settings", or a malformed "settings" payload)
            - 403 if the expo token is invalid
            - 500 if the device could not be persisted
    """
    try:
        data = json.loads(request.body)
    except ValueError as e:
        logger.error("Invalid JSON payload: %s", e)
        return JsonResponse({"error": "invalid JSON"}, status=400)
    logger.debug("Register payload: %s", data)
    try:
        token = data["expo_token"]
        settings = data["settings"]
    except KeyError as e:
        logger.error("Missing field in payload: %s", e)
        return JsonResponse({"error": f"missing field {e}"}, status=400)

    if not PushClient.is_exponent_push_token(token):
        logger.warning("Invalid expo token: %s", token)
        return JsonResponse({"error": "invalid expo token"}, status=403)

    # Validate the settings payload shape up front so a malformed client
    # request is reported as a 400, not masked as a 500 by the save block below.
    try:
        new_post = settings["new_post"]["value"]
        new_fact_check = settings["new_fact_check"]["value"]
        # Optional: older app versions don't send this key. Only update when
        # present so we keep the device's current value (default off).
        pruefpunkt = (
            settings.get("new_pruefpunkt") if isinstance(settings, dict) else None
        )
        new_pruefpunkt = (
            pruefpunkt["value"]
            if isinstance(pruefpunkt, dict) and "value" in pruefpunkt
            else None
        )
        if (
            not isinstance(new_post, bool)
            or not isinstance(new_fact_check, bool)
            or (new_pruefpunkt is not None and not isinstance(new_pruefpunkt, bool))
        ):
            raise TypeError("settings values must be boolean")
    except (KeyError, TypeError) as e:
        logger.warning("Invalid settings payload: %s", e)
        return JsonResponse({"error": "invalid settings"}, status=400)

    def meta(key: str, max_length: int) -> str | None:
        # None (key absent or not a string) leaves the stored value untouched.
        value = data.get(key)
        return value.strip()[:max_length] if isinstance(value, str) else None

    platform = meta("os", 50)
    app_build = meta("version", 50)

    try:
        device, created = NotificationDevice.objects.get_or_create(expo_token=token)
        device.notification_new_post = new_post
        device.notification_new_fact_check = new_fact_check
        if new_pruefpunkt is not None:
            device.notification_new_pruefpunkt = new_pruefpunkt
        if platform is not None:
            device.platform = platform
        if app_build is not None:
            device.app_build = app_build
        device.save()
    except Exception as e:
        logger.exception("Failed to save NotificationDevice: %s", e)
        return JsonResponse({"error": "internal error"}, status=500)
    logger.info(
        "Device %s %s for token %s",
        device.pk,
        "created" if created else "updated",
        token,
    )
    return JsonResponse({"status": "ok"})
