"""Views for the contact app."""

import json

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

from .asana import create_asana_task
from .models import ContactRequest

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
            Optional: app_variant, app_version, platform (client metadata).

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

    def meta(key: str, max_length: int) -> str:
        value = data.get(key)
        return value.strip()[:max_length] if isinstance(value, str) else ""

    filterset = {
        "category": category,
        "title": title[:500],
        "message": message,
        "app_variant": meta("app_variant", 100),
        "app_version": meta("app_version", 50),
        "platform": meta("platform", 50),
    }

    # Check if this exact request already exists (e.g. double tap on submit)
    contact_request = ContactRequest.objects.filter(**filterset).first()
    if not contact_request:
        contact_request = ContactRequest.objects.create(**filterset)
        label = CATEGORY_LABELS[ContactRequest.Category(category)]
        client = " | ".join(
            part
            for part in (
                contact_request.app_variant,
                contact_request.app_version,
                contact_request.platform,
            )
            if part
        )
        created = create_asana_task(
            name=f"{label} | {title}",
            notes=(
                f"{message}\n\n"
                f"Kategorie: {label}\n"
                f"App: {client or 'unbekannt'}\n"
                f"ID: {contact_request.id}"
            ),
            category=category,
        )
        if not created:
            # Roll back so a retry doesn't hit the dedupe path and report
            # success for a request that never reached Asana.
            contact_request.delete()
            return JsonResponse({"success": False}, status=502)
    return JsonResponse({"success": True, "id": contact_request.id})
