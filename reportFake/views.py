"""Views for the reportFake app.

LEGACY: current app versions submit fake reports through the generic
``contact`` app instead. Reports are forwarded to Asana; the endpoints
stay active for backward compatibility with older app versions.
"""

import json
import logging
import os
import uuid

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

from contact.asana import create_asana_task

from .models import FakeReport

logger = logging.getLogger(__name__)

# Create your views here.


def ratelimit_view(request: HttpRequest, exception: Exception):
    """View to handle rate limit exceptions."""
    return JsonResponse(
        {
            "success": False,
            "error": "Rate limit exceeded. Please try again later.",
        },
        status=429,
    )


@csrf_exempt
@ratelimit(key="ip", rate="1/m", method=["POST"], block=True)
@ratelimit(key="ip", rate="4/d", method=["POST"], block=True)
def reportFake(request: HttpRequest):
    """Report a fake news article.

    Args:
        request (Post Request):
            JSON body requires description, url, more_info

    Returns:
        JSONReponse: success, id of the report

    Rate limits:
        - 1 report per minute
        - 4 reports per day
    """
    # Check if rate limit was exceeded

    try:
        data = json.loads(request.body)
    except ValueError as e:
        logger.error("Invalid JSON payload: %s", e)
        return JsonResponse({"success": False, "error": "invalid JSON"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"success": False, "error": "invalid JSON"}, status=400)

    url = data.get("url")
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid URL format. URL must start with http:// or https://",
            },
            status=400,
        )

    filterset = {
        "description": data.get("description", None),
        "url": url,
        "more_info": data.get("more_info", None),
        "allowed_public": data.get("allowed_public", False),
        "token": data.get("token", None),
    }

    # Check if this exact report already exists
    report = FakeReport.objects.filter(**filterset).first()
    if not report:
        report = FakeReport.objects.create(**filterset)
    if not report.posted_to_asana:
        # Old app versions post here; put their reports on the same Asana
        # board as the contact app so fake reports converge in one inbox.
        created = create_asana_task(
            name=f"Fake-Report | {report.url}",
            notes=(
                f"{report.description or ''}\n\n"
                f"Weitere Links: {report.more_info or ''}\n"
                f"Kategorie: Fake-Report (Legacy-App)\n"
                f"ID: {report.id}"
            ),
            category="report_fake",
        )
        if not created:
            # Keep the row unposted so retries and concurrent duplicates
            # re-attempt the Asana post instead of deduping into success.
            # Non-2xx so the client doesn't show a false success screen
            # or poll /statusFake with a missing id.
            return JsonResponse({"success": False}, status=502)
        report.posted_to_asana = True
        report.save(update_fields=["posted_to_asana"])
    return JsonResponse({"success": True, "id": report.id})


def statusFake(request: HttpRequest, report_id: uuid.UUID):
    """Return JSON status of a report."""
    report = FakeReport.objects.filter(id=report_id).first()
    if not report:
        return JsonResponse({"error": "Not found"}, status=404)
    status = "posted" if report.post_id else "pending"
    handle = os.environ.get("BSKY_BOT_HANDLE", "")
    # Only build a URL when both the post id and the bot handle are known;
    # otherwise we'd produce an invalid ".../profile//post/..." link.
    url = (
        f"https://bsky.app/profile/{handle}/post/{report.post_id}"
        if report.post_id and handle
        else None
    )
    return JsonResponse({"id": report.id, "status": status, "url": url})
