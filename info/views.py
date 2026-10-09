import os

from django.http import HttpRequest, HttpResponse, JsonResponse

import vvp_app_server


def info(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "version": vvp_app_server.__version__,
            "build": os.environ.get("BUILD_SHA", "dev"),
            "date": os.environ.get("BUILD_DATE", "dev"),
            "env": os.environ.get("DEPLOY_ENV", "dev"),
        }
    )


# This domain only serves the app's API. Crawlers find the signed
# /proxy/media_url links embedded on volksverpetzer.de, mangle the query
# string and fill the logs with 400s, so keep all of them out.
def robots_txt(request: HttpRequest) -> HttpResponse:
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")
