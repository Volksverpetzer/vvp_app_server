"""Views for the reportFake app.

LEGACY / UNUSED: current app versions submit fake reports through the
generic ``contact`` app instead. This pipeline (report -> triage ->
Bluesky publish -> status polling) is kept for backward compatibility
with older app versions and in case we want to revive it later.
"""

import json
import logging
import os
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

from contact.asana import create_asana_task
from notifications.helper import send_push_message
from notifications.models import NotificationDevice

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

    data = json.loads(request.body)
    
    url = data.get("url")
    if not isinstance(url, str) or not url.lower().startswith(("http://", "https://")):
        return JsonResponse({"success": False, "error": "Invalid URL format. URL must start with http:// or https://"})

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
            # Roll back so a retry doesn't hit the dedupe path and report
            # success for a report that never reached Asana.
            report.delete()
            return JsonResponse({"success": False})
    return JsonResponse({"success": True, "id": report.id})


@login_required
def triageFake(request: HttpRequest):
    reports = list(
        FakeReport.objects.filter(
            post_id=None,
            description__isnull=False,
            allowed_public=True,  # Only show reports that haven't been archived
        )
        .exclude(description__exact="reportDescription")
        .order_by("-date")[:50]
    )
    return render(request, "reportFake/triage.html", {"reports": reports})


@login_required
def archiveFake(request: HttpRequest):
    if request.method == "POST":
        id = request.POST.get("report_id")
        print(id)
        report = FakeReport.objects.get(id=id)
        report.allowed_public = False
        report.save()
        return redirect("triageFake")
    else:
        logger.error("Invalid request method")
        return redirect("triageFake")


@login_required
def assign_bluesky(request: HttpRequest):
    if request.method == "POST":
        report_id = request.POST.get("report_id")
        bluesky_url = request.POST.get("bluesky_url")

        if not report_id or not bluesky_url:
            messages.error(request, "Missing required fields")
            return redirect("triageFake")
            
        # Validate URL to prevent XSS
        if not bluesky_url.lower().startswith(("http://", "https://")):
            messages.error(request, "Invalid URL format. URL must start with http:// or https://")
            return redirect("triageFake")

        try:
            report = FakeReport.objects.get(id=report_id)

            # Send notification to the user if they have a device token
            if report.token:
                try:
                    device = NotificationDevice.objects.get(token=report.token)
                    notification_title = "Dein Fake-Report wurde veröffentlicht"
                    notification_body = (
                        "Dein Fake-Report wurde auf Bluesky veröffentlicht. "
                        "Klicke hier, um ihn anzusehen."
                    )
                    send_push_message(
                        [device],
                        title=notification_title,
                        body=notification_body,
                        extra={"url": bluesky_url},
                    )
                except NotificationDevice.DoesNotExist:
                    logger.info(
                        "No notification device found for token: %s", report.token
                    )
                except Exception as e:
                    logger.error("Error sending notification: %s", str(e))

            messages.success(request, "Bluesky URL assigned successfully")
        except FakeReport.DoesNotExist:
            messages.error(request, "Report not found")
        except Exception as e:
            logger.error("Error assigning Bluesky URL: %s", str(e))
            messages.error(request, "An error occurred while assigning the Bluesky URL")

    return redirect("triageFake")


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


