import hashlib
import hmac
from typing import Any
import urllib.parse

from django.conf import settings
from django.http import HttpRequest
from django.urls import reverse


def generate_token(url: str) -> str:
    """
    Generate a secure hash token using HMAC with the Django secret and the URL.

    The HMAC is computed over the exact byte sequence of url with no
    percent-decoding. This binds the token to the precise URL string:
    "path%2Fmore" and "path/more" produce different tokens, which prevents
    an attacker from reusing a token by substituting a percent-encoded form
    that could resolve to a different authority (e.g. cdn%2F@evil.com).

    Callers must pass the same canonical form at signing time and at
    verification time. replace_media_urls signs the raw CDN URL; Django
    decodes the query parameter exactly once (symmetrically with
    urllib.parse.quote), so resolve_media_url receives the same string.
    """
    DJANGO_SECRET = settings.SECRET_KEY
    return hmac.new(DJANGO_SECRET.encode(), url.encode(), hashlib.sha256).hexdigest()


# Kept for tests only — do not use in production code.
def fully_unquote(url: str) -> str:
    """
    DEPRECATED: recursive unquoting collapsed %252F and %2F to the same string,
    causing HMAC token collisions. Retained for tests; use generate_token directly.
    """
    previous = url
    current = urllib.parse.unquote(previous)
    while current != previous:
        previous, current = current, urllib.parse.unquote(current)
    return current


def replace_media_urls(data: Any, request: HttpRequest) -> Any:
    """
    Recursively traverse the data structure and replace each 'media_url'
    and 'thumbnail_url' with a custom endpoint URL that includes the hash 
    and the original URL.
    """
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if key in ("media_url", "thumbnail_url") and isinstance(value, str):
                token = generate_token(value)
                # URL-encode the original media_url so it can be safely
                # embedded as a query parameter
                encoded_url = urllib.parse.quote(value, safe="")
                # Construct the new URL. This endpoint will check the token and
                # resolve the URL.
                custom_endpoint = request.build_absolute_uri(reverse("media_url"))
                new_value = f"{custom_endpoint}?hash={token}&url={encoded_url}"
                secure_url = new_value.replace("http://", "https://")
                new_data[key] = secure_url
            else:
                new_data[key] = replace_media_urls(value, request)
        return new_data
    elif isinstance(data, list):
        return [replace_media_urls(item, request) for item in data]
    else:
        return data
