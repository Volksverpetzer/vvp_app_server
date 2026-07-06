import html
import json
import logging
import os

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.crypto import constant_time_compare
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.db.models import Q

from notifications.models import PushMessageLog

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def notification_stats(request: HttpRequest):
    """Return delivery stats for a notification based on the Wordpress slug."""
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    parts = auth_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return HttpResponse(status=403)
    token = parts[1].strip()
    bearer = os.environ.get("NOTIFICATION_BEARER")
    if not bearer or not constant_time_compare(token, bearer):
        return HttpResponse(status=403)

    payload = {}
    if request.body:
        try:
            parsed = json.loads(request.body)
        except ValueError as exc:
            logger.error("Invalid JSON payload: %s", exc)
            return JsonResponse({"error": "invalid JSON"}, status=400)
        if not isinstance(parsed, dict):
            return JsonResponse({"error": "payload must be a JSON object"}, status=400)
        payload = parsed

    post_raw = payload.get("post")
    post = post_raw if isinstance(post_raw, dict) else {}
    slug = payload.get("slug") or post.get("post_name") or request.GET.get("slug")
    if not slug:
        return JsonResponse({"error": "missing slug"}, status=400)

    title_field = post.get("title")
    title_rendered = (
        title_field.get("rendered") if isinstance(title_field, dict) else None
    )
    post_title = post.get("post_title")
    raw_body = (
        (post_title if isinstance(post_title, str) else None)
        or (title_rendered if isinstance(title_rendered, str) else None)
        or ""
    )
    body = html.unescape(raw_body)
    if not body:
        return JsonResponse({"error": "missing post title"}, status=400)

    link_raw = post.get("link")
    url = link_raw.replace("\\/", "/") if isinstance(link_raw, str) else ""
    if url:
        exists = PushMessageLog.objects.filter(Q(data__url=url) | Q(body=body)).exists()
    else:
        exists = PushMessageLog.objects.filter(body=body).exists()

    return JsonResponse({"slug": slug, "success": exists})
