"""Views for the contact app."""

import json

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

from .asana import create_asana_task
from .models import ContactRequest

# Derived from the model so view validation can't drift from the DB limit
EMAIL_MAX_LENGTH = ContactRequest._meta.get_field("email").max_length or 254

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
    if not isinstance(data, dict):
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    category = data.get("category")
    if category not in ContactRequest.Category.values:
        return JsonResponse({"success": False, "error": "Invalid category"}, status=400)

    title = data.get("title")
    if not isinstance(title, str) or not title.strip():
        return JsonResponse({"success": False, "error": "Missing title"}, status=400)
    # Truncate once so the stored row and the Asana task always match
    title = title.strip()[:500]

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

    email = data.get("email")
    email = email.strip() if isinstance(email, str) else ""
    if email:
        # Reject (not truncate — a truncated address is useless) anything
        # longer than the EmailField's max_length; validate_email only
        # checks the format, not the total length.
        if len(email) > EMAIL_MAX_LENGTH:
            return JsonResponse(
                {"success": False, "error": "Invalid email"}, status=400
            )
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse(
                {"success": False, "error": "Invalid email"}, status=400
            )

    def meta(key: str, max_length: int) -> str:
        value = data.get(key)
        return value.strip()[:max_length] if isinstance(value, str) else ""

    fields = {
        "category": category,
        "title": title,
        "message": message,
        "app_variant": meta("app_variant", 100),
        "app_version": meta("app_version", 50),
        "platform": meta("platform", 50),
    }
    if email:
        # Only part of the payload (and dedupe hash) when provided, so
        # email-less submissions keep hashing like pre-email deployments
        fields["email"] = email

    # Dedupe double-submits atomically: the unique hash column collapses
    # concurrent identical POSTs into a single row (get_or_create retries
    # the lookup on IntegrityError).
    contact_request, _ = ContactRequest.objects.get_or_create(
        dedupe_hash=ContactRequest.build_dedupe_hash(**fields),
        defaults=fields,
    )
    if not contact_request.posted_to_asana:
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
                f"E-Mail: {contact_request.email or 'nicht angegeben'}\n"
                f"App: {client or 'unbekannt'}\n"
                f"ID: {contact_request.id}"
            ),
            category=category,
        )
        if not created:
            # Keep the row unposted so retries and concurrent duplicates
            # re-attempt the Asana post instead of deduping into success.
            return JsonResponse({"success": False}, status=502)
        contact_request.posted_to_asana = True
        contact_request.save(update_fields=["posted_to_asana"])
    return JsonResponse({"success": True, "id": contact_request.id})
