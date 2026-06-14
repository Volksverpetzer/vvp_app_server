import html
import json
import logging
import os

import requests
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_q.tasks import (  # type: ignore[reportMissingTypeStubs]
    async_task,
    delete_group,
    queue_size,
)

from notifications.models import NotificationDevice

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_new_post(request: HttpRequest):
    """Send new notification.

    Args:
        request (django request): django POST request from wordpress webhook plugin

    Returns:
        JsonResponse (200): notification batches scheduled successfully
        HttpResponse (403): missing or invalid Bearer token
        JsonResponse (400): invalid JSON body or missing required fields (post.post_name)
        HttpResponse (405): non-POST request (enforced by @require_http_methods)
        HttpResponse (503): upstream WordPress API error or post not found
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return HttpResponse(status=403)
    token = parts[1].strip()
    bearer = os.environ.get("NOTIFICATION_BEARER")
    if not bearer or not constant_time_compare(token, bearer):
        return HttpResponse(status=403)

    try:
        data = json.loads(request.body)
    except ValueError as exc:
        logger.error("Invalid JSON payload: %s", exc)
        return JsonResponse({"error": "invalid JSON"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "payload must be a JSON object"}, status=400)
    post_data = data.get("post")
    post_name = post_data.get("post_name") if isinstance(post_data, dict) else None
    if not isinstance(post_name, str) or not post_name.strip():
        return JsonResponse({"error": "missing post.post_name"}, status=400)
    slug = post_name.strip()
    wpUrl = (
        os.environ["WP_URL"] if "WP_URL" in os.environ else "https://volksverpetzer.de"
    )
    appName = os.environ["APP_NAME"] if "APP_NAME" in os.environ else "Volksverpetzer"
    try:
        response = requests.get(
            wpUrl + "/wp-json/wp/v2/posts/",
            params={"slug": slug},
            headers={"User-Agent": "VVP APP Server"},
            timeout=10,
        )
        response.raise_for_status()
        posts = response.json()
    except requests.exceptions.RequestException as exc:
        logger.error("WordPress API request failed: %s", exc)
        return HttpResponse(status=503, content="Upstream error")
    except ValueError as exc:
        logger.error("WordPress API returned non-JSON response: %s", exc)
        return HttpResponse(status=503, content="Upstream error")
    if not isinstance(posts, list) or len(posts) == 0:
        return HttpResponse(status=503, content="Post does not exist")
    post = posts[0]
    if not isinstance(post, dict):
        return HttpResponse(status=503, content="Upstream error")
    yoast = post.get("yoast_head_json")
    yoast = yoast if isinstance(yoast, dict) else {}
    og = yoast.get("og_image") or []
    image_url = og[0].get("url") if isinstance(og, list) and og and isinstance(og[0], dict) else None
    image_url = image_url if isinstance(image_url, str) else None
    title_field = post.get("title")
    title = html.unescape(title_field.get("rendered", "") if isinstance(title_field, dict) else "")

    qs = NotificationDevice.objects.order_by("id")

    taxonomies = data.get("taxonomies")
    category_raw = taxonomies.get("category") if isinstance(taxonomies, dict) else None
    categories = category_raw if isinstance(category_raw, dict) else {}
    isFactCheck = "faktencheck" in categories
    if isFactCheck:
        qs = qs.filter(notification_new_fact_check=True)
    else:
        qs = qs.filter(notification_new_post=True)
    logger.debug("Queue size: %s", queue_size())
    delete_group("notifications")
    paginator = Paginator(qs, 100)
    for page in paginator.page_range:
        devices = paginator.page(page).object_list
        try:
            logger.info("scheduling notification batch")
            link_raw = post.get("link")
            extra = {"url": link_raw.replace("\\/", "/") if isinstance(link_raw, str) else ""}
            if image_url:
                extra["richContent"] = {"image": image_url.replace("\\/", "/")}

            async_task(
                "notifications.helper.send_push_message_delayed",
                devices,
                appName + (" | Faktencheck" if isFactCheck else " | Beitrag"),
                title,
                extra=extra,
                group="notifications",
            )
        except Exception as e:
            logger.exception("Error in notification batch: %s", e)

    return JsonResponse({"status": "ok"})
