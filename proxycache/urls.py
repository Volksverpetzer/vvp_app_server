# Urls Routing Django
from django.urls import path

from .services.analytics import faves, links
from .services.analytics import map as map_view
from .services.analytics import regions, shares, stats
from .services.bluesky_feed import blueskyFeed
from .services.insta_feed import instaById, instaFeed
from .services.insta_meme_feed import instaMemeFeed
from .services.resolve_media_url import resolve_media_url
from .services.tiktok_feed import tiktokFeed
from .services.youtube_api import ytAPI

urlpatterns = [
    path("instaFeed", instaFeed, name="instaFeed"),
    path("blueskyFeed", blueskyFeed, name="blueSkyFeed"),
    path("instaMemeFeed", instaMemeFeed, name="instaMemeFeed"),
    path("instaById/<str:id>", instaById, name="instaById"),
    path("ytAPI", ytAPI, name="ytAPI"),
    path("shares", shares, name="shares_base"),
    path("links/<path:remaining>/", links, name="links"),
    path("map", map_view, name="map"),
    # Plausible proxy endpoints
    path("stats/<path:remaining>/", stats, name="stats"),
    path("favs/<path:remaining>/", faves, name="favs"),
    path("regions", regions, name="regions"),
    path("tiktokFeed", tiktokFeed, name="tiktokFeed"),
    path("media_url", resolve_media_url, name="media_url"),
    path("shares/<path:path>", shares, name="shares"),
]
