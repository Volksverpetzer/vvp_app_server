import os

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from googleapiclient.discovery import build  # type: ignore[reportMissingTypeStubs]

from vvp_app_server.cache_utils import cache_response

# Volksverpetzer YouTube channel; overridable via the YT_CHANNEL_ID env var
# (e.g. for the Mimikama deployment).
DEFAULT_CHANNEL_ID = "UC9qdoYTVU413M6EvqDRZDtA"


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
        part="snippet,player",
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
        if (
            "snippet" in video
            and "description" in video["snippet"]
            and "#shorts" not in video["snippet"]["description"]
        ):
            # Set player dimensions such that width is greater than height
            video["player"] = {
                "width": 854,  # Example width
                "height": 480,  # Example height
            }
            filtered_videos.append(video)

    # Create a new response with filtered videos
    filtered_response = {"items": filtered_videos, "time": timezone.now().isoformat()}

    return JsonResponse(filtered_response)
