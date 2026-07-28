import os
import re

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from googleapiclient.discovery import build  # type: ignore[reportMissingTypeStubs]

from vvp_app_server.cache_utils import cache_response

# Volksverpetzer YouTube channel; overridable via the YT_CHANNEL_ID env var
# (e.g. for the Mimikama deployment).
DEFAULT_CHANNEL_ID = "UC9qdoYTVU413M6EvqDRZDtA"

# YouTube classifies videos at or under this length as Shorts.
SHORT_MAX_SECONDS = 180

_ISO8601_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _duration_seconds(iso_duration: str) -> int:
    """Parse an ISO 8601 duration (e.g. "PT1M30S") into whole seconds.

    Returns 0 (treated as a Short by the caller) if the string doesn't match.
    """
    match = _ISO8601_DURATION_RE.match(iso_duration or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(g) if g else 0 for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 30)
def ytAPI(request: HttpRequest):
    """Retrieve Youtube Feed.

    Returns:
       JsonResponse: Youtube Feed
    """
    # .strip() so a stray-whitespace env value falls back to the default
    # instead of being sent to the API as a malformed channel id (→ 500).
    channel_id = os.environ.get("YT_CHANNEL_ID", "").strip() or DEFAULT_CHANNEL_ID
    youtube = build("youtube", "v3", developerKey=os.environ["YT_ACCESS_TOKEN"])
    yt_request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        safeSearch="none",
        order="date",
        maxResults=40,
    )
    yt_response = yt_request.execute()
    if yt_response["items"] == []:
        return JsonResponse({"items": [], "time": timezone.now().isoformat()})
    yt_request = youtube.videos().list(
        part="snippet,player,contentDetails",
        id=",".join(
            [
                item["id"]["videoId"]
                for item in yt_response["items"]
                if "videoId" in item["id"]
            ]
        ),
        maxResults=20,
    )
    yt_response = yt_request.execute()
    filtered_videos = []
    for video in yt_response["items"]:
        duration = video.get("contentDetails", {}).get("duration", "")
        # Filter by actual duration (YouTube's own Shorts definition) rather
        # than the old "#shorts" description heuristic, which let genuine
        # Shorts without that tag through.
        if "snippet" in video and _duration_seconds(duration) >= SHORT_MAX_SECONDS:
            # Set player dimensions such that width is greater than height
            video["player"] = {
                "width": 854,  # Example width
                "height": 480,  # Example height
            }
            filtered_videos.append(video)

    # Create a new response with filtered videos
    filtered_response = {"items": filtered_videos, "time": timezone.now().isoformat()}

    return JsonResponse(filtered_response)
