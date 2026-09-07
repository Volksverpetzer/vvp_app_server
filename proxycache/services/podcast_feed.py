import os
from datetime import timezone as datetime_timezone
from email.utils import parsedate_to_datetime

import defusedxml.ElementTree as ElementTree
import requests
from defusedxml.common import DefusedXmlException
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from vvp_app_server.cache_utils import cache_response

DEFAULT_FEED_URL = "https://volksverpetzer.podigee.io/feed/mp3"


def get_feed_url() -> str:
    """The podcast RSS feed URL, overridable via the PODCAST_FEED_URL env var
    (e.g. for the Mimikama deployment or a feed move).

    .strip() so a stray-whitespace env value falls back to the default rather
    than being fetched as a malformed URL.
    """
    return os.environ.get("PODCAST_FEED_URL", "").strip() or DEFAULT_FEED_URL

ITUNES_NS = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


def _parse_duration(raw: str | None) -> int | None:
    """Parse an itunes:duration value (plain seconds or [HH:]MM:SS) to seconds."""
    if not raw:
        return None
    try:
        parts = [int(part) for part in raw.split(":")]
    except ValueError:
        return None
    # Reject shapes itunes:duration doesn't define (more than H:M:S, negatives)
    # instead of folding them into a nonsense value.
    if len(parts) > 3 or any(part < 0 for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + part
    return seconds


def parse_podcast_feed(content: bytes) -> list[dict]:
    """Parse a Podigee RSS feed into a flat list of episode dicts."""
    root = ElementTree.fromstring(content)
    channel = root.find("channel")
    if channel is None:
        return []
    channel_image = channel.findtext("image/url")
    episodes = []
    for item in channel.findall("item"):
        enclosure = item.find("enclosure")
        audio_url = enclosure.get("url") if enclosure is not None else None
        # An episode without audio is useless to the app player
        if not audio_url:
            continue
        published_at = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                parsed = parsedate_to_datetime(pub_date)
                # RFC 2822 "-0000" yields a naive datetime; emit it as UTC so
                # the app never interprets the timestamp as device-local time.
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=datetime_timezone.utc)
                published_at = parsed.isoformat()
            except (TypeError, ValueError):
                published_at = None
        image = item.find(f"{ITUNES_NS}image")
        image_url = image.get("href") if image is not None else None
        episodes.append(
            {
                "id": (item.findtext("guid") or "").strip() or audio_url,
                "title": (item.findtext("title") or "").strip(),
                "description": (item.findtext("description") or "").strip(),
                "published_at": published_at,
                "link": (item.findtext("link") or "").strip() or None,
                "audio_url": audio_url,
                "image_url": image_url or channel_image,
                "duration": _parse_duration(item.findtext(f"{ITUNES_NS}duration")),
            }
        )
    return episodes


# Constant cache key: the endpoint takes no parameters, so keying on the full
# path would let arbitrary query strings bypass the cache (and evict other
# entries from the shared cache) for no benefit.
@cache_response(lambda request, *args, **kwargs: "podcastFeed", 60 * 30)
def podcastFeed(request: HttpRequest):
    """Retrieve the Podigee podcast feed as JSON.

    Returns:
        JsonResponse: {"episodes": [...], "time": ...}
    """
    try:
        response = requests.get(get_feed_url(), timeout=15)
        response.raise_for_status()
        episodes = parse_podcast_feed(response.content)
    except (
        requests.exceptions.RequestException,
        ElementTree.ParseError,
        DefusedXmlException,
    ):
        # Controlled 502 instead of an uncaught 500: cache_response never
        # caches non-200s, so a transient Podigee outage is not replayed.
        return HttpResponse(status=502)
    return JsonResponse({"episodes": episodes, "time": timezone.now().isoformat()})
