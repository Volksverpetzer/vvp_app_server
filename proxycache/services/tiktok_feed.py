import os
from datetime import timedelta

import requests
from django.http import HttpRequest, JsonResponse
from django.utils.timezone import now
from django.views.decorators.http import require_GET

from proxycache.models import TiktokToken


@require_GET
def tiktokFeed(request: HttpRequest) -> JsonResponse:
    """Stub: TikTok feed integration is not implemented; always returns empty."""
    return JsonResponse({"data": {"data": {"videos": []}}})


def refreshTiktokToken(token_obj: TiktokToken | None = None):
    """Refresh TikTok tokens using DB or env refresh_token."""
    refresh = (
        token_obj.refresh_token if token_obj else os.environ.get("TIKTOK_REFRESH_TOKEN")
    )
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        timeout=5,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": refresh,
        },
    )
    data = resp.json()
    return data.get("access_token"), data.get("refresh_token"), data.get("expires_in")


def getTiktokToken():
    """Retrieve valid access token, refreshing or creating record as needed."""
    token_obj = TiktokToken.objects.last()
    now_dt = now()
    if token_obj:
        expiry = token_obj.date + timedelta(seconds=token_obj.expires_in)
        if now_dt >= expiry:
            access, refresh, expires = refreshTiktokToken(token_obj)
            (
                token_obj.token,
                token_obj.refresh_token,
                token_obj.expires_in,
                token_obj.date,
            ) = (access, refresh, expires, now_dt)
            token_obj.save()
            return access
        return token_obj.token
    # no token: fetch using env refresh_token
    access, refresh, expires = refreshTiktokToken()
    TiktokToken.objects.create(
        token=access, refresh_token=refresh, expires_in=expires, date=now_dt
    )
    return access
