import os

from atproto import Client  # type: ignore[reportMissingTypeStubs]
from atproto_client.models.app.bsky.feed.defs import FeedViewPost, ReasonRepost  # type: ignore[reportMissingTypeStubs]
from django.http import HttpRequest, JsonResponse

from vvp_app_server.cache_utils import cache_response

DEFAULT_ACCOUNT = "volksverpetzer"

ACCOUNTS = {
    "volksverpetzer": {"handle_env": "BSKY_HANDLE", "pwd_env": "BSKY_PWD"},
    "pruefpunkt": {"handle_env": "BSKY_HANDLE_PRUEFPUNKT", "pwd_env": "BSKY_PWD_PRUEFPUNKT"},
    "bot": {"handle_env": "BSKY_BOT_HANDLE", "pwd_env": "BSKY_BOT_PWD"},
}


def _resolve_account(request: HttpRequest) -> tuple[str, JsonResponse | None]:
    account = request.GET.get("account", DEFAULT_ACCOUNT)
    if account not in ACCOUNTS:
        return "", JsonResponse({"error": "invalid account"}, status=400)
    return account, None


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 10)
def blueskyFeed(request: HttpRequest):
    account, err = _resolve_account(request)
    if err:
        return err
    cfg = ACCOUNTS[account]
    handle = os.environ.get(cfg["handle_env"])
    password = os.environ.get(cfg["pwd_env"])
    if not handle or not password:
        # The account is known but its credentials aren't configured on this
        # deployment (e.g. the optional pruefpunkt/bot accounts). Return a
        # controlled error instead of an uncaught KeyError / 500.
        return JsonResponse({"error": "account not configured"}, status=503)
    client = Client()
    client.login(handle, password)
    did = client.com.atproto.identity.resolve_handle({"handle": handle}).did
    feed_1 = client.app.bsky.feed.get_author_feed({"actor": did, "limit": 100})
    feed_2 = client.app.bsky.feed.get_author_feed(
        {"actor": did, "limit": 100, "cursor": feed_1.cursor}
    )
    feed_3 = client.app.bsky.feed.get_author_feed(
        {"actor": did, "limit": 100, "cursor": feed_2.cursor}
    )
    feed = feed_1.feed + feed_2.feed + feed_3.feed
    filtered_feed: list[FeedViewPost] = []
    for item in feed:
        if not isinstance(item.reason, ReasonRepost):
            filtered_feed.append(item)

    return JsonResponse({"feed": [item.model_dump() for item in filtered_feed]})
