import hashlib
import hmac
import json
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


def generate_token_with_context(
    url: str, post_id: str, child_id: str, account: str
) -> str:
    """
    Like generate_token(), but also binds the token to the Instagram post
    (and, for a carousel slide, the child) it came from, plus the account
    whose API token can re-fetch it. This lets resolve_media_url look up a
    fresh media_url from Instagram when the embedded signed CDN URL has
    since expired — Instagram issues some (typically older) media
    noticeably shorter-lived signed URLs than others fetched in the same
    batch, so a URL can already be dead by the time a visitor loads it even
    though our own cache is still within its TTL.

    JSON-encoded rather than concatenated so the signature can't be
    confused by any of these values containing a separator character.
    """
    DJANGO_SECRET = settings.SECRET_KEY
    payload = json.dumps(
        {"url": url, "post_id": post_id, "child_id": child_id, "account": account},
        sort_keys=True,
    )
    return hmac.new(
        DJANGO_SECRET.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


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


def replace_media_urls_for_posts(
    posts: list, request: HttpRequest, account: str
) -> list:
    """
    Instagram-feed-specific counterpart to replace_media_urls(): rewrites
    each post's 'media_url'/'thumbnail_url', and each carousel child's
    'media_url', into a proxy URL — binding the post id (and, for a child,
    the child id) and account into the signature so resolve_media_url can
    re-fetch a fresh URL from Instagram if the embedded one has expired by
    the time it's requested. A post missing an 'id' (shouldn't happen, but
    the field is technically optional in the API response) falls back to
    the plain, context-free signature instead — same as a link generated
    before this existed.
    """
    custom_endpoint = request.build_absolute_uri(reverse("media_url"))

    def _proxy_url(url: str, post_id: str, child_id: str) -> str:
        encoded_url = urllib.parse.quote(url, safe="")
        if post_id:
            token = generate_token_with_context(url, post_id, child_id, account)
            q_post_id = urllib.parse.quote(post_id, safe="")
            q_account = urllib.parse.quote(account, safe="")
            extra = f"&post_id={q_post_id}&account={q_account}"
            if child_id:
                extra += f"&child_id={urllib.parse.quote(child_id, safe='')}"
        else:
            token = generate_token(url)
            extra = ""
        new_value = f"{custom_endpoint}?hash={token}&url={encoded_url}{extra}"
        return new_value.replace("http://", "https://")

    new_posts = []
    for post in posts:
        if not isinstance(post, dict):
            new_posts.append(post)
            continue

        new_post = dict(post)
        post_id = str(post.get("id") or "")

        for key in ("media_url", "thumbnail_url"):
            value = new_post.get(key)
            if isinstance(value, str):
                new_post[key] = _proxy_url(value, post_id, "")

        children = new_post.get("children")
        if isinstance(children, dict) and isinstance(children.get("data"), list):
            new_children_data = []
            for child in children["data"]:
                if not isinstance(child, dict):
                    new_children_data.append(child)
                    continue
                new_child = dict(child)
                child_id = str(child.get("id") or "")
                value = new_child.get("media_url")
                if isinstance(value, str):
                    new_child["media_url"] = _proxy_url(value, post_id, child_id)
                new_children_data.append(new_child)
            new_post["children"] = {**children, "data": new_children_data}

        new_posts.append(new_post)
    return new_posts
