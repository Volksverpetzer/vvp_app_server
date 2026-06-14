import os

from atproto import Client  # type: ignore[reportMissingTypeStubs]
from atproto_client.models.app.bsky.feed.defs import FeedViewPost, ReasonRepost  # type: ignore[reportMissingTypeStubs]
from django.http import HttpRequest, JsonResponse

from vvp_app_server.cache_utils import cache_response


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 10)
def blueskyFeed(request: HttpRequest):
    USERNAME = os.environ["BSKY_HANDLE"]
    PASSWORD = os.environ["BSKY_PWD"]
    client = Client()
    client.login(USERNAME, PASSWORD)
    did = client.com.atproto.identity.resolve_handle({"handle": USERNAME}).did
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
