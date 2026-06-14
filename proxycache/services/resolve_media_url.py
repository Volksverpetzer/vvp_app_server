import hashlib
import hmac

import requests
from django.core.cache import cache
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)

from ..helper import generate_token


def resolve_media_url(request: HttpRequest):
    provided_hash = request.GET.get("hash")
    # Django decodes the query parameter once, restoring the original URL that
    # replace_media_urls encoded with urllib.parse.quote(value, safe="").
    # No further unquoting is needed or correct.
    media_url = request.GET.get("url")

    if not provided_hash or not media_url:
        return HttpResponseBadRequest("Missing required parameters.")

    expected_hash = generate_token(media_url)

    if not hmac.compare_digest(provided_hash, expected_hash):
        return HttpResponseForbidden("Invalid token.")

    cache_key = (
        "resolve_media_url:" + hashlib.sha256(request.get_full_path().encode()).hexdigest()
    )
    cached = cache.get(cache_key)
    if cached:
        return HttpResponse(cached["content"], content_type=cached["content_type"])

    try:
        response = requests.get(media_url, timeout=10)
        response.raise_for_status()
    except Exception:
        return HttpResponseBadRequest("Failed to fetch media URL.")

    content_type = response.headers.get("Content-Type", "application/octet-stream")
    cache.set(
        cache_key,
        {"content": response.content, "content_type": content_type},
        60 * 60 * 24 * 7,
    )
    return HttpResponse(response.content, content_type=content_type)
