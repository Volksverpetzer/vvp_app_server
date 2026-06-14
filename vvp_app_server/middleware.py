from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse


class EdgeCacheControlMiddleware(MiddlewareMixin):
    """Sets Cache-Control headers: no cache for authenticated views, caching for public GETs."""

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
        # Cache other GET responses on the edge
        elif request.method == "GET" and response.status_code == 200:
            response["Cache-Control"] = "public, max-age=300"
        return response
