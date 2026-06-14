"""Views for the reportFake app."""

import json
import logging
import os
import uuid

import requests
from atproto import Client  # type: ignore[reportMissingTypeStubs]
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import (  # type: ignore[reportMissingTypeStubs]
    ratelimit,
)

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
        api_key = os.environ.get("MAILGUN_TOKEN")
        domain = os.environ.get("MAILGUN_DOMAIN")
        receiver = os.environ.get("MAILGUN_RECEIVER")
        if not api_key or not domain or not receiver:
            return JsonResponse({"success": False})
        result = requests.post(
            f"https://api.eu.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": f"Excited User <mailgun@{domain}>",
                "to": [receiver],
                "subject": f"Fake Report | {report.id}",
                "text": (
                    f"{report.description}, {report.url}, "
                    f"{report.more_info}, {report.id}"
                ),
            },
            timeout=10,
        )
        if result.status_code != 200:
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
            report.bluesky_url = bluesky_url
            report.save(update_fields=["bluesky_url"])

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
    handle = os.environ.get("BOT_BSKY_HANDLE", "")
    url = report.post_id and (
        f"https://bsky.app/profile/{handle}/post/" f"{report.post_id}"
    )
    return JsonResponse({"id": report.id, "status": status, "url": url})


def botFeed(request: HttpRequest):
    """Fetch and return bot's Bluesky posts."""
    BOT_HANDLE = os.environ.get("BOT_BSKY_HANDLE", "")
    BOT_PWD = os.environ.get("BOT_BSKY_PWD", "")
    client = Client()
    client.login(BOT_HANDLE, BOT_PWD)
    did = client.com.atproto.identity.resolve_handle({"handle": BOT_HANDLE}).did
    feed = []
    resp1 = client.app.bsky.feed.get_author_feed({"actor": did, "limit": 100})
    feed.extend(resp1.feed)
    if resp1.cursor:
        resp2 = client.app.bsky.feed.get_author_feed(
            {"actor": did, "limit": 100, "cursor": resp1.cursor}
        )
        feed.extend(resp2.feed)
    # filter out reposts
    from atproto_client.models.app.bsky.feed.defs import (  # type: ignore[reportMissingTypeStubs]
        ReasonRepost,
    )

    posts = [
        item.model_dump() for item in feed if not isinstance(item.reason, ReasonRepost)
    ]
    return JsonResponse({"feed": posts})
