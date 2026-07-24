import os
import urllib.parse
from unittest.mock import MagicMock, patch

import requests

from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from proxycache.helper import fully_unquote, generate_token, replace_media_urls
from proxycache.models import InstaToken, TiktokToken

# Create your tests here.


class ProxyTest(TestCase):
    c = Client(enforce_csrf_checks=True)

    def setUp(self):
        self.c = Client(enforce_csrf_checks=True)

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta(self, mock_get, mock_refresh):
        mock_get.return_value.json.return_value = {"data": []}
        mock_refresh.return_value = ("dummy_token", 3600)  # nosec
        InstaToken.objects.create(
            token="dummy_token",
            expires_in=3600,  # nosec
        )
        response = self.c.get("/proxy/instaFeed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args[1]["params"]["access_token"], "dummy_token")
        response2 = self.c.get("/proxy/instaFeed")
        self.assertEqual(response.json(), response2.json())

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta_account_param_uses_account_token(self, mock_get, mock_refresh):
        mock_get.return_value.json.return_value = {"data": []}
        mock_refresh.return_value = ("dummy_token", 3600)  # nosec
        InstaToken.objects.create(
            token="vvp_token",
            expires_in=3600,  # nosec
        )
        InstaToken.objects.create(
            token="pp_token",  # nosec
            expires_in=3600,
            account="pruefpunkt",
        )
        response = self.c.get("/proxy/instaFeed?account=pruefpunkt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args[1]["params"]["access_token"], "pp_token")

    def test_cache_response_skips_error_bodies(self):
        # An upstream that returns a 200 body containing an "error" key (e.g.
        # Bluesky) must not be cached and replayed. Tested at the cache layer
        # directly, independent of any view's status-code handling.
        from django.http import JsonResponse

        from vvp_app_server.cache_utils import cache_response

        calls = {"n": 0}

        @cache_response(lambda request, *a, **k: request.get_full_path(), 600)
        def view(request):
            calls["n"] += 1
            return JsonResponse({"error": {"code": 190}})

        req = RequestFactory().get("/dummy-error-cache-test")
        view(req)
        view(req)
        # error body not cached: the wrapped view is re-invoked each time
        self.assertEqual(calls["n"], 2)

    def test_insta_invalid_account(self):
        response = self.c.get("/proxy/instaFeed?account=unknown")
        self.assertEqual(response.status_code, 400)
        # error responses must not be cached and replayed as 200
        response2 = self.c.get("/proxy/instaFeed?account=unknown")
        self.assertEqual(response2.status_code, 400)

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta_upstream_error_returns_502(self, mock_get, mock_refresh):
        # upstream keeps returning an error even after the token retry
        mock_get.return_value.json.return_value = {"error": {"code": 190}}
        mock_refresh.return_value = ("new_token", 3600)  # nosec
        response = self.c.get("/proxy/instaFeed?case=upstream-error")
        self.assertEqual(response.status_code, 502)
        # the retry refreshed the token once
        self.assertEqual(mock_get.call_count, 2)

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta_by_id_upstream_error_returns_502(self, mock_get, mock_refresh):
        mock_get.return_value.json.return_value = {"error": {"code": 190}}
        mock_refresh.return_value = ("new_token", 3600)  # nosec
        response = self.c.get("/proxy/instaById/999?case=upstream-error")
        self.assertEqual(response.status_code, 502)

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta_by_id_account_param(self, mock_get, mock_refresh):
        mock_get.return_value.json.return_value = {"media_type": "IMAGE"}
        mock_refresh.return_value = ("dummy_token", 3600)  # nosec
        InstaToken.objects.create(
            token="pp_token",  # nosec
            expires_in=3600,
            account="pruefpunkt",
        )
        response = self.c.get("/proxy/instaById/123?account=pruefpunkt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args[1]["params"]["access_token"], "pp_token")

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    def test_initialize_token_updates_existing_row(self, mock_refresh):
        from proxycache.services.insta_feed import initializeToken

        mock_refresh.return_value = ("first_token", 3600)  # nosec
        initializeToken()
        mock_refresh.return_value = ("second_token", 3600)  # nosec
        initializeToken()
        tokens = InstaToken.objects.filter(account="volksverpetzer")
        self.assertEqual(tokens.count(), 1)
        self.assertEqual(tokens.get().token, "second_token")
        # other accounts get their own row
        initializeToken("pruefpunkt")
        self.assertEqual(InstaToken.objects.count(), 2)

    @patch("proxycache.services.insta_feed.requests.get")
    def test_insta_env_token_fallback_per_account(self, mock_get):
        mock_get.return_value.json.return_value = {"data": []}
        with patch.dict(
            os.environ,
            {
                "INSTAGRAM_ACCESS_TOKEN": "vvp_env_token",
                "INSTAGRAM_ACCESS_TOKEN_PRUEFPUNKT": "pp_env_token",
            },
        ):
            response = self.c.get("/proxy/instaFeed?account=volksverpetzer")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                mock_get.call_args[1]["params"]["access_token"], "vvp_env_token"
            )

            response = self.c.get("/proxy/instaFeed?account=pruefpunkt&cachebust=env")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                mock_get.call_args[1]["params"]["access_token"], "pp_env_token"
            )

    @patch("proxycache.services.insta_feed.refreshInstaToken")
    def test_get_token_partial_refresh_falls_back_to_env(self, mock_refresh):
        from proxycache.services.insta_feed import getToken

        # expired stored token
        InstaToken.objects.create(token="stale_token", expires_in=0)  # nosec
        # refresh returns a token but no expires_in
        mock_refresh.return_value = ("half_refreshed", None)  # nosec
        with patch.dict(os.environ, {"INSTAGRAM_ACCESS_TOKEN": "env_token"}):
            self.assertEqual(getToken(), "env_token")
        # the stored row was not corrupted by the partial refresh result
        self.assertEqual(InstaToken.objects.get().token, "stale_token")

    def test_tiktok(self):
        # mock tiktok API request
        with patch("proxycache.services.tiktok_feed.requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"data": []}

        # mock tiktok token in DB
        TiktokToken.objects.create(
            token="dummy_token",
            expires_in=3600,  # nosec
        )

        response = self.c.get("/tiktok/tiktokFeed")
        # check if the response is 200 OK.
        self.assertEqual(response.status_code, 200)
        response2 = self.c.get("/tiktok/tiktokFeed")
        self.assertEqual(response.json(), response2.json())

    def test_resolve_media_url_missing_params(self):
        response = self.c.get("/proxy/media_url")
        self.assertEqual(response.status_code, 400)

    def test_resolve_media_url_invalid_hash(self):
        orig = "http://example.com/img.png"
        encoded = urllib.parse.quote(orig)
        response = self.c.get(f"/proxy/media_url?hash=wrong&url={encoded}")
        self.assertEqual(response.status_code, 403)

    def test_resolve_media_url_success(self):
        orig = "http://example.com/img.png"
        encoded = urllib.parse.quote(orig)
        expected_hash = generate_token(orig)
        fake_content = b"binarydata"
        fake_ct = "image/png"
        with patch("proxycache.services.resolve_media_url.requests.get") as mock_get:
            mock_get.return_value.content = fake_content
            mock_get.return_value.headers = {"Content-Type": fake_ct}
            response = self.c.get(
                f"/proxy/media_url?hash={expected_hash}&url={encoded}"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, fake_content)
        self.assertEqual(response["Content-Type"], fake_ct)

    def test_generate_token_helper(self):
        with override_settings(SECRET_KEY="dummy_secret"):  # nosec
            token = generate_token("http://example.com")
            import hashlib
            import hmac

            expected = hmac.new(
                b"dummy_secret", b"http://example.com", hashlib.sha256
            ).hexdigest()
            self.assertEqual(token, expected)

    def test_fully_unquote(self):
        # double-encoded url
        encoded = urllib.parse.quote(urllib.parse.quote("a b"))
        result = fully_unquote(encoded)
        self.assertEqual(result, "a b")

    def test_replace_media_urls(self):
        rf = RequestFactory()
        request = rf.get("/")
        base = request.build_absolute_uri(reverse("media_url"))
        # secure base with https as replace_media_urls enforces
        secure_base = base.replace("http://", "https://")
        orig = "http://example.com/img.png"
        data = {
            "media_url": orig,
            "nested": [
                {"media_url": orig},
                "keep",
            ],
            "other": "value",
        }
        new = replace_media_urls(data, request)
        # Check top-level
        self.assertTrue(new["media_url"].startswith(secure_base))
        # token matches generate_token
        token = generate_token(orig)
        self.assertIn(f"hash={token}", new["media_url"])
        # Check nested list
        self.assertTrue(new["nested"][0]["media_url"].startswith(secure_base))
        # Other values unchanged
        self.assertEqual(new["other"], "value")

    def test_replace_media_urls_thumbnail(self):
        rf = RequestFactory()
        request = rf.get("/")
        secure_base = request.build_absolute_uri(reverse("media_url")).replace(
            "http://", "https://"
        )
        orig = "http://example.com/thumb.jpg"
        data = {"thumbnail_url": orig, "media_url": orig}
        new = replace_media_urls(data, request)
        token = generate_token(orig)
        self.assertTrue(new["thumbnail_url"].startswith(secure_base))
        self.assertIn(f"hash={token}", new["thumbnail_url"])
        self.assertTrue(new["media_url"].startswith(secure_base))

    def test_resolve_media_url_with_percent_encoded_url(self):
        # A raw URL that itself contains percent-encoded characters (%2F).
        # replace_media_urls encodes this with quote(safe=""), so the query param
        # carries %252F. Django decodes once back to %2F. The HMAC must be computed
        # against that Django-decoded value (i.e. the original raw URL) both at
        # signing and at verification time.
        orig = "http://example.com/path%2Fmore.png"
        encoded = urllib.parse.quote(orig, safe="")
        expected_hash = generate_token(orig)
        fake_content = b"imgdata"
        with patch("proxycache.services.resolve_media_url.requests.get") as mock_get:
            mock_get.return_value.content = fake_content
            mock_get.return_value.headers = {"Content-Type": "image/png"}
            mock_get.return_value.raise_for_status = lambda: None
            response = self.c.get(
                f"/proxy/media_url?hash={expected_hash}&url={encoded}"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, fake_content)
        # Assert the upstream fetch used the original percent-encoded URL,
        # not a further-decoded variant (e.g. %2F must not become /).
        mock_get.assert_called_once_with(orig, timeout=10)

    def test_generate_token_double_vs_single_encoded_differ(self):
        # %252F and %2F must produce different HMACs — the old fully_unquote
        # decoded both recursively to "/" and collapsed them to the same token.
        token_double = generate_token("http://example.com/path%252Fmore")
        token_single = generate_token("http://example.com/path%2Fmore")
        self.assertNotEqual(token_double, token_single)

    def test_generate_token_decoded_vs_encoded_differ(self):
        # %2F and its decoded form "/" must produce different HMACs. Without this
        # guarantee an attacker could take a signed token for cdn.example/@host/path
        # and submit cdn.example%2F@host/path — which Python's requests library
        # treats as a different authority — and the HMAC would still verify.
        token_decoded = generate_token("http://cdn.example/@host/path")
        token_encoded = generate_token("http://cdn.example%2F@host/path")
        self.assertNotEqual(token_decoded, token_encoded)

    def test_youtube_api(self):
        # mock youtube API request and ensure filtering and player injection
        with patch.dict(os.environ, {"YT_ACCESS_TOKEN": "dummy_token"}):  # nosec
            with patch("proxycache.services.youtube_api.build") as mock_build:
                mock_youtube = MagicMock()
                mock_build.return_value = mock_youtube
                # mock search.list().execute()
                mock_search = mock_youtube.search.return_value
                mock_search.list.return_value.execute.return_value = {
                    "items": [{"id": {"videoId": "v1"}}, {"id": {}}]
                }
                # mock videos.list().execute()
                mock_videos = mock_youtube.videos.return_value
                mock_videos.list.return_value.execute.return_value = {
                    "items": [
                        {"snippet": {"description": "desc"}},
                        {"snippet": {"description": "#shorts hide"}},
                        {},
                    ]
                }
                # call endpoint
                response = self.c.get("/proxy/ytAPI")
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn("items", data)
                items = data["items"]
                self.assertEqual(len(items), 1)
                video = items[0]
                self.assertIn("player", video)
                self.assertEqual(video["player"]["width"], 854)
                self.assertEqual(video["player"]["height"], 480)
                # cached response same
                response2 = self.c.get("/proxy/ytAPI")
                self.assertEqual(data, response2.json())

    def test_youtube_channel_id_defaults_and_env_override(self):
        def run(env, bust, unset_channel=False):
            # patch.dict snapshots os.environ and restores it on exit, so both
            # the injected keys and the pop below are undone afterwards — no
            # cross-test pollution even if the real env sets YT_CHANNEL_ID.
            with patch.dict(os.environ, env):  # nosec
                if unset_channel:
                    os.environ.pop("YT_CHANNEL_ID", None)
                with patch("proxycache.services.youtube_api.build") as mock_build:
                    mock_youtube = MagicMock()
                    mock_build.return_value = mock_youtube
                    mock_youtube.search.return_value.list.return_value.execute.return_value = {  # noqa: E501
                        "items": []
                    }
                    # Unique query string keeps each call off the shared cache.
                    self.c.get(f"/proxy/ytAPI?cachebust={bust}")
                    return mock_youtube.search.return_value.list.call_args[1][
                        "channelId"
                    ]

        default_channel = "UC9qdoYTVU413M6EvqDRZDtA"
        # Default channel when unset
        self.assertEqual(
            run({"YT_ACCESS_TOKEN": "dummy"}, "default", unset_channel=True),  # nosec
            default_channel,
        )
        # Env override wins
        self.assertEqual(
            run({"YT_ACCESS_TOKEN": "dummy", "YT_CHANNEL_ID": "UC_custom"}, "custom"),  # nosec
            "UC_custom",
        )
        # Whitespace-only value falls back to the default instead of being sent
        # to the API as a malformed channel id
        self.assertEqual(
            run({"YT_ACCESS_TOKEN": "dummy", "YT_CHANNEL_ID": "   "}, "ws"),  # nosec
            default_channel,
        )


class AnalyticsSiteTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _mock_plausible(self, mock_post, value=42):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"metrics": [value], "dimensions": []}]
        }
        mock_post.return_value = mock_resp

    def _mock_wp(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [{"date_gmt": "2024-01-01T00:00:00"}]
        mock_get.return_value = mock_resp

    # --- shares ---

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_shares_no_site_defaults_to_vvp(self, _cg, _cs, mock_post):
        self._mock_plausible(mock_post)
        response = self.client.get(reverse("shares_base"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "volksverpetzer.de")

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_shares_pruefpunkt_site(self, _cg, _cs, mock_post):
        self._mock_plausible(mock_post)
        response = self.client.get(reverse("shares_base") + "?site=pruefpunkt.org")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "pruefpunkt.org")

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    def test_shares_invalid_site_returns_400(self):
        response = self.client.get(reverse("shares_base") + "?site=evil.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid site"})

    # --- stats ---

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.requests.get")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_stats_no_site_defaults_to_vvp(self, _cg, _cs, mock_get, mock_post):
        self._mock_plausible(mock_post)
        self._mock_wp(mock_get)
        response = self.client.get(reverse("stats", args=["slug"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "volksverpetzer.de")
        self.assertIn("volksverpetzer.de", mock_get.call_args[0][0])

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.requests.get")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_stats_pruefpunkt_site(self, _cg, _cs, mock_get, mock_post):
        self._mock_plausible(mock_post)
        self._mock_wp(mock_get)
        response = self.client.get(
            reverse("stats", args=["slug"]) + "?site=pruefpunkt.org"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "pruefpunkt.org")
        self.assertIn("pruefpunkt.org", mock_get.call_args[0][0])

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    def test_stats_invalid_site_returns_400(self):
        response = self.client.get(reverse("stats", args=["slug"]) + "?site=evil.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid site"})

    # --- faves ---

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_faves_no_site_defaults_to_vvp(self, _cg, _cs, mock_post):
        self._mock_plausible(mock_post)
        response = self.client.get(reverse("favs", args=["slug"]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "volksverpetzer.de")

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    @patch("proxycache.services.analytics.requests.post")
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.cache_get", return_value=None)
    def test_faves_pruefpunkt_site(self, _cg, _cs, mock_post):
        self._mock_plausible(mock_post)
        response = self.client.get(
            reverse("favs", args=["slug"]) + "?site=pruefpunkt.org"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "pruefpunkt.org")

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    def test_faves_invalid_site_returns_400(self):
        response = self.client.get(reverse("favs", args=["slug"]) + "?site=evil.com")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid site"})


class AnalyticsLinksTest(TestCase, Client):
    def setUp(self):
        # use real PLAUSIBLE_TOKEN from environment
        self.client = Client()

    @patch("proxycache.services.analytics.cache_get", return_value=None)
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.requests.post")
    def test_links_view_returns_links(
        self, mock_post: MagicMock, mock_cache_set: MagicMock, mock_cache_get: MagicMock
    ):
        # mock Plausible API response
        category = "foo"
        slug = "bar"
        page = f"/{category}/{slug}/"
        fake_results = [{"metrics": [5], "dimensions": [page]}]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": fake_results}
        mock_post.return_value = mock_resp

        url = reverse("links", args=[f"{category}/{slug}"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # result should map dimensions to url
        expected = {"links": [{"visitors": 5, "url": page}]}
        self.assertEqual(response.json(), expected)
        # no site param defaults to the primary site
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "volksverpetzer.de")

    @patch("proxycache.services.analytics.cache_get", return_value=None)
    @patch("proxycache.services.analytics.cache_set")
    @patch("proxycache.services.analytics.requests.post")
    def test_links_view_pruefpunkt_site(
        self, mock_post: MagicMock, mock_cache_set: MagicMock, mock_cache_get: MagicMock
    ):
        page = "/foo/bar/"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"metrics": [5], "dimensions": [page]}]
        }
        mock_post.return_value = mock_resp

        url = reverse("links", args=["foo/bar"]) + "?site=pruefpunkt.org"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_post.call_args[1]["json"]["site_id"], "pruefpunkt.org")

    @patch.dict(os.environ, {"PLAUSIBLE_TOKEN": "test"})  # nosec
    def test_links_view_invalid_site_returns_400(self):
        url = reverse("links", args=["foo/bar"]) + "?site=evil.com"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "invalid site"})


class AnalyticsMapTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("proxycache.services.analytics.cache_get")
    @override_settings(RATELIMIT_ENABLE=False)
    def test_map_cache_hit_skips_computation(self, mock_cache_get):
        fake_img = b"\x89PNG\r\n\x1a\n"
        mock_cache_get.return_value = {"data": fake_img}
        response = self.client.get(reverse("map"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, fake_img)
        self.assertEqual(response["Content-Type"], "image/png")

    @patch("proxycache.services.analytics.cache_get")
    def test_map_rate_limit_blocks_after_five_requests(self, mock_cache_get):
        fake_img = b"\x89PNG\r\n\x1a\n"
        mock_cache_get.return_value = {"data": fake_img}
        for _ in range(5):
            r = self.client.get(reverse("map"))
            self.assertEqual(r.status_code, 200)
        blocked = self.client.get(reverse("map"))
        self.assertEqual(blocked.status_code, 429)


class CacheUtilsTest(TestCase):
    def test_cache_get_warms_memory_from_persistent(self):
        from django.core.cache import caches
        from vvp_app_server.cache_utils import cache_get

        key = "test_warm_up_key"
        caches["default"].delete(key)
        caches["persistent"].set(key, {"x": 1}, 60)
        result = cache_get(key)
        self.assertEqual(result, {"x": 1})
        self.assertEqual(caches["default"].get(key), {"x": 1})

    def test_cache_response_replays_list_body(self):
        import json

        from django.http import JsonResponse
        from django.test import RequestFactory
        from vvp_app_server.cache_utils import cache_response

        calls = []

        @cache_response(lambda req: "list_body_key", 60)
        def list_view(request):
            calls.append(1)
            return JsonResponse([1, 2], safe=False)

        rf = RequestFactory()
        response = list_view(rf.get("/"))
        self.assertEqual(json.loads(response.content), [1, 2])
        # second call is served from the cache and must not crash on the
        # non-dict body
        response2 = list_view(rf.get("/"))
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(json.loads(response2.content), [1, 2])
        self.assertEqual(len(calls), 1)

    def test_cache_response_non_json_passes_through(self):
        from django.http import HttpResponse
        from django.test import RequestFactory
        from vvp_app_server.cache_utils import cache_response

        @cache_response(lambda req: "non_json_key", 60)
        def binary_view(request):
            return HttpResponse(b"\x89PNG", content_type="image/png")

        rf = RequestFactory()
        request = rf.get("/")
        response = binary_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"\x89PNG")


class TiktokHelperTest(TestCase):
    @patch("proxycache.services.tiktok_feed.requests.post")
    @patch.dict(
        os.environ,
        {
            "TIKTOK_CLIENT_KEY": "k",
            "TIKTOK_CLIENT_SECRET": "s",
            "TIKTOK_REFRESH_TOKEN": "rt",
        },
    )
    def test_refresh_tiktok_token_from_env(self, mock_post):
        mock_post.return_value.json.return_value = {
            "access_token": "acc",
            "refresh_token": "ref",
            "expires_in": 3600,
        }
        from proxycache.services.tiktok_feed import refreshTiktokToken

        access, refresh, expires = refreshTiktokToken()
        self.assertEqual(access, "acc")
        self.assertEqual(refresh, "ref")
        self.assertEqual(expires, 3600)

    @patch("proxycache.services.tiktok_feed.requests.post")
    @patch.dict(os.environ, {"TIKTOK_CLIENT_KEY": "k", "TIKTOK_CLIENT_SECRET": "s"})
    def test_get_tiktok_token_creates_record_when_none_exists(self, mock_post):
        mock_post.return_value.json.return_value = {
            "access_token": "new_acc",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        from proxycache.models import TiktokToken
        from proxycache.services.tiktok_feed import getTiktokToken

        TiktokToken.objects.all().delete()
        with patch.dict(os.environ, {"TIKTOK_REFRESH_TOKEN": "rt"}):
            token = getTiktokToken()
        self.assertEqual(token, "new_acc")
        self.assertTrue(TiktokToken.objects.exists())

    @patch("proxycache.services.tiktok_feed.requests.post")
    @patch.dict(os.environ, {"TIKTOK_CLIENT_KEY": "k", "TIKTOK_CLIENT_SECRET": "s"})
    def test_get_tiktok_token_refreshes_expired_token(self, mock_post):
        from datetime import timedelta
        from django.utils.timezone import now
        from proxycache.models import TiktokToken
        from proxycache.services.tiktok_feed import getTiktokToken

        TiktokToken.objects.all().delete()
        TiktokToken.objects.create(
            token="old_token", refresh_token="old_ref", expires_in=1
        )
        # auto_now ignores date in create(); use update() to set it in the past
        TiktokToken.objects.update(date=now() - timedelta(seconds=60))
        mock_post.return_value.json.return_value = {
            "access_token": "refreshed",
            "refresh_token": "new_ref",
            "expires_in": 3600,
        }
        token = getTiktokToken()
        self.assertEqual(token, "refreshed")


class BlueskyFeedAccountTest(TestCase):
    def setUp(self):
        self.client = Client()

    @patch("proxycache.services.bluesky_feed.Client")
    def test_default_account_uses_vvp_env(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.com.atproto.identity.resolve_handle.return_value = MagicMock(
            did="did:vvp"
        )
        mock_client.app.bsky.feed.get_author_feed.return_value = MagicMock(
            feed=[], cursor=None
        )
        with patch.dict(
            os.environ, {"BSKY_HANDLE": "vvp.bsky.social", "BSKY_PWD": "vvp_pass"}
        ):  # nosec
            response = self.client.get("/proxy/blueskyFeed")
        self.assertEqual(response.status_code, 200)
        mock_client.login.assert_called_once_with("vvp.bsky.social", "vvp_pass")

    @patch("proxycache.services.bluesky_feed.Client")
    def test_pruefpunkt_account_uses_pruefpunkt_env(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.com.atproto.identity.resolve_handle.return_value = MagicMock(
            did="did:pp"
        )
        mock_client.app.bsky.feed.get_author_feed.return_value = MagicMock(
            feed=[], cursor=None
        )
        with patch.dict(
            os.environ,
            {
                "BSKY_HANDLE_PRUEFPUNKT": "pp.bsky.social",
                "BSKY_PWD_PRUEFPUNKT": "pp_pass",
            },
        ):  # nosec
            response = self.client.get(
                "/proxy/blueskyFeed?account=pruefpunkt&cachebust=pp"
            )
        self.assertEqual(response.status_code, 200)
        mock_client.login.assert_called_once_with("pp.bsky.social", "pp_pass")

    @patch("proxycache.services.bluesky_feed.Client")
    def test_bot_account_uses_bot_env(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.com.atproto.identity.resolve_handle.return_value = MagicMock(
            did="did:bot"
        )
        mock_client.app.bsky.feed.get_author_feed.return_value = MagicMock(
            feed=[], cursor=None
        )
        with patch.dict(
            os.environ,
            {"BSKY_BOT_HANDLE": "bot.bsky.social", "BSKY_BOT_PWD": "bot_pass"},
        ):  # nosec
            response = self.client.get("/proxy/blueskyFeed?account=bot&cachebust=bot")
        self.assertEqual(response.status_code, 200)
        mock_client.login.assert_called_once_with("bot.bsky.social", "bot_pass")

    def test_invalid_account_returns_400(self):
        response = self.client.get("/proxy/blueskyFeed?account=unknown&cachebust=inv")
        self.assertEqual(response.status_code, 400)


PODCAST_FEED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
  <channel>
    <title>Volksverpetzer - der Podcast</title>
    <image>
      <url>https://example.com/channel.png</url>
    </image>
    <item>
      <title>Folge 24: Testfolge</title>
      <description>Beschreibung der Folge.
</description>
      <pubDate>Fri, 26 Jun 2026 04:00:00 +0000</pubDate>
      <link>https://volksverpetzer.podigee.io/25-folge-24</link>
      <guid isPermaLink="false">abc123</guid>
      <itunes:image href="https://example.com/episode.png"/>
      <enclosure url="https://audio.example.com/ep24.mp3" type="audio/mpeg" length="1"/>
      <itunes:duration>3539</itunes:duration>
    </item>
    <item>
      <title>Folge ohne Audio</title>
      <guid>no-audio</guid>
    </item>
    <item>
      <title>Folge mit HH:MM:SS Dauer</title>
      <guid>hms</guid>
      <enclosure url="https://audio.example.com/ep23.mp3" type="audio/mpeg" length="1"/>
      <itunes:duration>01:02:03</itunes:duration>
    </item>
  </channel>
</rss>
"""


class PodcastFeedTest(TestCase):
    c = Client(enforce_csrf_checks=True)

    def setUp(self):
        # The endpoint uses a constant cache key, so cached responses would
        # leak between tests without an explicit clear.
        from django.core.cache import cache

        cache.clear()

    def test_parse_podcast_feed(self):
        from proxycache.services.podcast_feed import parse_podcast_feed

        episodes = parse_podcast_feed(PODCAST_FEED_XML)
        # Episode without an enclosure is dropped
        self.assertEqual(len(episodes), 2)
        first = episodes[0]
        self.assertEqual(first["id"], "abc123")
        self.assertEqual(first["title"], "Folge 24: Testfolge")
        self.assertEqual(first["description"], "Beschreibung der Folge.")
        self.assertEqual(first["published_at"], "2026-06-26T04:00:00+00:00")
        self.assertEqual(first["link"], "https://volksverpetzer.podigee.io/25-folge-24")
        self.assertEqual(first["audio_url"], "https://audio.example.com/ep24.mp3")
        self.assertEqual(first["image_url"], "https://example.com/episode.png")
        self.assertEqual(first["duration"], 3539)
        # HH:MM:SS duration and channel image fallback
        second = episodes[1]
        self.assertEqual(second["duration"], 3723)
        self.assertEqual(second["image_url"], "https://example.com/channel.png")

    def test_parse_naive_pubdate_is_treated_as_utc(self):
        from proxycache.services.podcast_feed import parse_podcast_feed

        # RFC 2822 "-0000" produces a naive datetime in parsedate_to_datetime;
        # the parser must emit it with an explicit UTC offset so the app never
        # interprets it as device-local time.
        xml = PODCAST_FEED_XML.replace(b"+0000", b"-0000")
        episodes = parse_podcast_feed(xml)
        self.assertEqual(episodes[0]["published_at"], "2026-06-26T04:00:00+00:00")

    def test_parse_duration_rejects_garbage(self):
        from proxycache.services.podcast_feed import _parse_duration

        self.assertEqual(_parse_duration("3539"), 3539)
        self.assertEqual(_parse_duration("01:02:03"), 3723)
        self.assertIsNone(_parse_duration("-5"))
        self.assertIsNone(_parse_duration("1:2:3:4"))
        self.assertIsNone(_parse_duration("abc"))
        self.assertIsNone(_parse_duration(""))
        self.assertIsNone(_parse_duration(None))

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_endpoint(self, mock_get):
        mock_get.return_value.content = PODCAST_FEED_XML
        response = self.c.get("/proxy/podcastFeed")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["episodes"]), 2)
        self.assertEqual(body["episodes"][0]["id"], "abc123")
        mock_get.assert_called_once()
        self.assertEqual(
            mock_get.call_args[0][0], "https://volksverpetzer.podigee.io/feed/mp3"
        )
        self.assertIn("timeout", mock_get.call_args[1])

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_url_env_override(self, mock_get):
        mock_get.return_value.content = PODCAST_FEED_XML
        with patch.dict(
            os.environ, {"PODCAST_FEED_URL": "https://example.com/other-feed"}
        ):
            response = self.c.get("/proxy/podcastFeed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_get.call_args[0][0], "https://example.com/other-feed")

    def test_get_feed_url_whitespace_falls_back_to_default(self):
        from proxycache.services.podcast_feed import DEFAULT_FEED_URL, get_feed_url

        with patch.dict(os.environ, {"PODCAST_FEED_URL": "   "}):
            self.assertEqual(get_feed_url(), DEFAULT_FEED_URL)
        with patch.dict(os.environ, {"PODCAST_FEED_URL": ""}):
            self.assertEqual(get_feed_url(), DEFAULT_FEED_URL)

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_is_cached_and_ignores_query_strings(self, mock_get):
        mock_get.return_value.content = PODCAST_FEED_XML
        first = self.c.get("/proxy/podcastFeed")
        second = self.c.get("/proxy/podcastFeed?bust=1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        # Constant cache key: a query string must not bypass the cache
        mock_get.assert_called_once()

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_upstream_error_returns_502(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")
        response = self.c.get("/proxy/podcastFeed")
        self.assertEqual(response.status_code, 502)

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_malformed_xml_returns_502(self, mock_get):
        mock_get.return_value.content = b"<html>Podigee error page</html><oops"
        response = self.c.get("/proxy/podcastFeed")
        self.assertEqual(response.status_code, 502)

    @patch("proxycache.services.podcast_feed.requests.get")
    def test_podcast_feed_error_is_not_cached(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("down")
        self.assertEqual(self.c.get("/proxy/podcastFeed").status_code, 502)
        # Upstream recovers: the next request must fetch fresh data instead of
        # replaying the failure.
        mock_get.side_effect = None
        mock_get.return_value.content = PODCAST_FEED_XML
        response = self.c.get("/proxy/podcastFeed")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["episodes"]), 2)
