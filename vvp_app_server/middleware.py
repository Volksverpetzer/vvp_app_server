from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse


class EdgeCacheControlMiddleware(MiddlewareMixin):
    """Set Cache-Control headers.

    No caching for authenticated views or redirects; caching for public GETs.

    Must sit above SecurityMiddleware: its SECURE_SSL_REDIRECT 301 is returned
    before inner middleware runs, so this would otherwise never see it.
    """

    def process_response(
        self, request: HttpRequest, response: HttpResponse
    ) -> HttpResponse:
        # Respect manual Cache-Control headers
        if response.has_header("Cache-Control"):
            return response
        # Do not cache responses for authenticated users
        if hasattr(request, "user") and request.user.is_authenticated:
            response["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        # Never let the edge cache redirects. A 301 that Bunny cached while
        # it reached the origin without X-Forwarded-Proto pointed back at the
        # requested https URL itself, sending clients into a redirect loop
        # until the cache was purged.
        elif 300 <= response.status_code < 400:
            response["Cache-Control"] = "no-store"
        # Cache other GET responses on the edge
        elif request.method == "GET" and response.status_code == 200:
            response["Cache-Control"] = "public, max-age=300"
        return response
