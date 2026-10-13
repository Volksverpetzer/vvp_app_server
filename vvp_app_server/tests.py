from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, override_settings

from .middleware import EdgeCacheControlMiddleware


class EdgeCacheControlMiddlewareTests(SimpleTestCase):
    def _process(self, response: HttpResponse) -> HttpResponse:
        request = RequestFactory().get("/proxy/favs/some/slug/")
        return EdgeCacheControlMiddleware(lambda _: response)(request)

    def test_public_get_is_edge_cached(self):
        response = self._process(HttpResponse("ok"))
        self.assertEqual(response["Cache-Control"], "public, max-age=300")

    def test_redirect_is_not_cached(self):
        response = self._process(HttpResponseRedirect("/elsewhere/"))
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_not_modified_is_not_marked_no_store(self):
        response = self._process(HttpResponse(status=304))
        self.assertFalse(response.has_header("Cache-Control"))

    def test_manual_cache_control_is_kept(self):
        original = HttpResponseRedirect("/elsewhere/")
        original["Cache-Control"] = "max-age=60"
        response = self._process(original)
        self.assertEqual(response["Cache-Control"], "max-age=60")

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_https_redirect_is_not_cached(self):
        # SecurityMiddleware short-circuits with this 301 before any inner
        # middleware runs, so this only passes while EdgeCacheControl is
        # ordered above it.
        response = self.client.get("/proxy/regions")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].startswith("https://"))
        self.assertEqual(response["Cache-Control"], "no-store")
