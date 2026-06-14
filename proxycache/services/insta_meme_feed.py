import os
import time

import requests
from django.http import HttpRequest, JsonResponse

from vvp_app_server.cache_utils import cache_response


@cache_response(lambda request, *args, **kwargs: request.get_full_path(), 60 * 10)
def instaMemeFeed(request: HttpRequest):
    """Retrieve Instagram meme feed."""
    url = "https://graph.instagram.com/v15.0/me/media"
    params = {
        "limit": 20,
        "fields": "id,permalink,media_type,caption,timestamp,children{media_url},media_url",
        "access_token": os.environ["INSTAGRAM_MEME_TOKEN"],
    }
    response = requests.get(url=url, params=params, timeout=10)
    instaData = response.json()
    
    # If there's an error in the response, return empty data array
    if "error" in instaData:
        return JsonResponse({"data": []})
    
    instaData["timestamp"] = time.time()
    return JsonResponse(instaData)
