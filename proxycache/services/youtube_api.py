import os
from datetime import datetime

from django.http import HttpRequest, JsonResponse
from googleapiclient.discovery import build  # type: ignore[reportMissingTypeStubs]

from vvp_app_server.cache_utils import cache_response


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 30)
def ytAPI(request: HttpRequest):
    """Retrieve Youtube Feed.

    Returns:
       JsonResponse: Youtube Feed
    """
    channel_id = "UC9qdoYTVU413M6EvqDRZDtA"
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
        return JsonResponse({"items": [], "time": datetime.now().isoformat()})
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
    filtered_response = {"items": filtered_videos, "time": datetime.now().isoformat()}

    return JsonResponse(filtered_response)
