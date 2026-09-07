import os
import time
from datetime import timedelta

import requests
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.timezone import now

from proxycache.helper import replace_media_urls_for_posts
from proxycache.models import InstaToken
from vvp_app_server.cache_utils import cache_response

DEFAULT_ACCOUNT = "volksverpetzer"

# Supported Instagram accounts and the env var holding their initial token.
ACCOUNTS = {
    "volksverpetzer": {"token_env": "INSTAGRAM_ACCESS_TOKEN"},
    "pruefpunkt": {"token_env": "INSTAGRAM_ACCESS_TOKEN_PRUEFPUNKT"},
}


def _resolve_account(request: HttpRequest) -> tuple[str, JsonResponse | None]:
    account = request.GET.get("account", DEFAULT_ACCOUNT)
    if account not in ACCOUNTS:
        return "", JsonResponse({"error": "invalid account"}, status=400)
    return account, None


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 10)
def instaFeed(request: HttpRequest) -> JsonResponse | HttpResponse:
    """
    Retrieve Instagram feed of the requested account (?account=, defaults to
    volksverpetzer) using its stored token.
    """
    account, err = _resolve_account(request)
    if err:
        return err
    url = "https://graph.instagram.com/v15.0/me/media"
    params = {
        "limit": 20,
        "fields": (
            "id,permalink,media_type,caption,timestamp,"
            "children{id,media_url},media_url,thumbnail_url"
        ),
        "access_token": getToken(account),
    }
    try:
        response = requests.get(url=url, params=params, timeout=10)
        raw_data = response.json()
        if isinstance(raw_data, dict) and "error" in raw_data:
            initializeToken(account)
            params["access_token"] = getToken(account)
            response = requests.get(url=url, params=params, timeout=10)
            raw_data = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return HttpResponse(status=502)
    if isinstance(raw_data, dict) and "error" in raw_data:
        # the token refresh did not help: don't serve the upstream error
        # payload as a cacheable 200
        return HttpResponse(status=502)
    if not isinstance(raw_data, dict):
        # return error
        return HttpResponse(status=500)
    posts = raw_data.get("data")
    if isinstance(posts, list):
        raw_data["data"] = replace_media_urls_for_posts(posts, request, account)
    raw_data.pop("paging", None)
    raw_data["timestamp"] = time.time()
    return JsonResponse(raw_data)


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 10)
def instaById(request: HttpRequest, id: str) -> JsonResponse | HttpResponse:
    """Retrieve Instagram Feed item by ID (?account= selects the account)."""
    account, err = _resolve_account(request)
    if err:
        return err
    url = f"https://graph.instagram.com/v15.0/{id}"
    params = {
        "fields": (
            "permalink,media_type,caption,timestamp,"
            "children{media_url},media_url,thumbnail_url"
        ),
        "access_token": getToken(account),
    }
    try:
        response = requests.get(url=url, params=params, timeout=10)
        raw_data = response.json()
        if isinstance(raw_data, dict) and "error" in raw_data:
            initializeToken(account)
            params["access_token"] = getToken(account)
            response = requests.get(url=url, params=params, timeout=10)
            raw_data = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return HttpResponse(status=502)
    if isinstance(raw_data, dict) and "error" in raw_data:
        # the token refresh did not help: don't serve the upstream error
        # payload as a cacheable 200
        return HttpResponse(status=502)
    if not isinstance(raw_data, dict):
        return JsonResponse(raw_data, safe=False)
    raw_data["timestamp"] = time.time()
    return JsonResponse(raw_data)


def fetch_fresh_media_url(post_id: str, child_id: str, account: str) -> str | None:
    """
    Re-fetch a single Instagram post (or, with child_id, one of its carousel
    children) to get a freshly signed CDN media_url. Used by
    resolve_media_url as a one-shot retry when the previously embedded URL
    has expired — see generate_token_with_context() for why that happens
    even within our own cache's TTL. Returns None on any failure; the
    caller already has a plain fetch-failed response to fall back to, so
    there's no token-refresh-and-retry dance here like instaFeed/instaById
    have — this is a best-effort last resort, not the primary path.
    """
    if account not in ACCOUNTS or not post_id:
        return None
    try:
        token = getToken(account)
    except requests.exceptions.RequestException:
        # getToken() refreshes the stored token when expired; a network
        # error during that refresh shouldn't turn this best-effort retry
        # into an unhandled 500.
        return None
    url = f"https://graph.instagram.com/v15.0/{post_id}"
    params = {
        "fields": "media_url,thumbnail_url,children{id,media_url}",
        "access_token": token,
    }
    try:
        response = requests.get(url=url, params=params, timeout=10)
        data = response.json()
    except (requests.exceptions.RequestException, ValueError):
        return None
    if not isinstance(data, dict) or "error" in data:
        return None
    if child_id:
        for child in data.get("children", {}).get("data", []):
            if isinstance(child, dict) and str(child.get("id") or "") == child_id:
                return child.get("media_url")
        return None
    return data.get("media_url") or data.get("thumbnail_url")


def envToken(account: str = DEFAULT_ACCOUNT):
    """Return the initial token of the account from the environment."""
    return os.environ.get(ACCOUNTS[account]["token_env"])


def refreshInstaToken(
    token_obj: InstaToken | None = None, account: str = DEFAULT_ACCOUNT
):
    """Refresh Instagram token using existing token_obj or env token."""
    access = token_obj.token if token_obj else envToken(account)
    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": access},
        timeout=10,
    )
    data = resp.json()
    return data.get("access_token"), data.get("expires_in")


def initializeToken(account: str = DEFAULT_ACCOUNT):
    """Initialize or update the Instagram token of the account in DB."""
    token, expires = refreshInstaToken(account=account)
    if not token or not expires:
        return
    # update the active row instead of growing the table on every re-init
    # (e.g. when the views re-initialize on repeated upstream errors)
    obj = InstaToken.objects.filter(account=account).order_by("date").last()
    if obj:
        obj.token, obj.expires_in = token, expires
        obj.save()
    else:
        InstaToken.objects.create(token=token, expires_in=expires, account=account)


def getToken(account: str = DEFAULT_ACCOUNT):
    """Return the stored token of the account if still valid; refresh it when
    expired. Fall back to the env token when no token is stored or the
    refresh failed."""
    token = InstaToken.objects.filter(account=account).order_by("date").last()
    if token:
        expiry = token.date + timedelta(seconds=token.expires_in)
        # return stored token if not expired
        if now() < expiry:
            return token.token
        # expired: refresh and update (date is auto_now, set on save)
        new_val, new_exp = refreshInstaToken(token, account)
        if new_val and new_exp:
            token.token, token.expires_in = new_val, new_exp
            token.save()
            return new_val
    # no token or failed refresh: return env token
    return envToken(account)
