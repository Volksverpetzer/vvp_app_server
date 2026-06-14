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
            dictionary with two keys: "new_post" and "new_fact_check". Each
            of these is a dictionary with one key: "value".

    Returns:
        JSONResponse: 200 if sucess, 403 if not
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

    try:
        device, created = NotificationDevice.objects.get_or_create(expo_token=token)
        device.notification_new_post = settings["new_post"]["value"]
        device.notification_new_fact_check = settings["new_fact_check"]["value"]
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
