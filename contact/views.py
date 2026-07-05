"""Views for the contact app."""

import json
import logging

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

from .asana import create_asana_task
from .models import ContactRequest

logger = logging.getLogger(__name__)

CATEGORY_LABELS = {
    ContactRequest.Category.REPORT_FAKE: "Fake-Report",
    ContactRequest.Category.APP_FEEDBACK: "App-Feedback",
    ContactRequest.Category.OTHER: "Sonstiges",
}


@csrf_exempt
@ratelimit(key="ip", rate="1/m", method=["POST"], block=True)
@ratelimit(key="ip", rate="10/d", method=["POST"], block=True)
def contact(request: HttpRequest):
    """Submit a contact request and post it to the Asana board.

    Args:
        request (Post Request):
            JSON body requires category (report_fake | app_feedback | other),
            title (the reported URL for report_fake) and message.
            Optional: token (push notification token).

    Returns:
        JSONResponse: success, id of the contact request

    Rate limits:
        - 1 request per minute
        - 10 requests per day
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    category = data.get("category")
    if category not in ContactRequest.Category.values:
        return JsonResponse(
            {"success": False, "error": "Invalid category"}, status=400
        )

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return JsonResponse({"success": False, "error": "Missing title"}, status=400)
    title = title.strip()

    if category == ContactRequest.Category.REPORT_FAKE and not title.lower().startswith(
        ("http://", "https://")
    ):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid URL format. URL must start with http:// or https://",
            },
            status=400,
        )

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({"success": False, "error": "Missing message"}, status=400)
    message = message.strip()

    filterset = {
        "category": category,
        "title": title[:500],
        "message": message,
        "token": data.get("token", None),
    }

    # Check if this exact request already exists (e.g. double tap on submit)
    contact_request = ContactRequest.objects.filter(**filterset).first()
    if not contact_request:
        contact_request = ContactRequest.objects.create(**filterset)
        label = CATEGORY_LABELS[ContactRequest.Category(category)]
        created = create_asana_task(
            name=f"{label} | {title}",
            notes=f"{message}\n\nKategorie: {label}\nID: {contact_request.id}",
        )
        if not created:
            return JsonResponse({"success": False}, status=502)
    return JsonResponse({"success": True, "id": contact_request.id})
