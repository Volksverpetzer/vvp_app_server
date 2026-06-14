import os

from django.http import HttpRequest, JsonResponse

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
