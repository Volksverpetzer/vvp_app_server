import hashlib
import os

import requests
from django.http import HttpRequest, JsonResponse

from vvp_app_server.cache_utils import cache_get, cache_set


def googleFact(request: HttpRequest) -> JsonResponse:
    token = os.environ.get("GOOGLE_FACT")
    claims = []
    cache_key = hashlib.sha256(request.get_full_path().encode()).hexdigest()
    if cache_get(cache_key):
        return JsonResponse(cache_get(cache_key))
    if "keywords" not in request.GET:
        return JsonResponse({"claims": []})
    else:
        keywords = request.GET.get("keywords", "")
        url = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
        response = requests.get(
            url,
            params={"query": keywords, "key": token, "languageCode": "de"},
            timeout=10,
        )
        data = response.json()
        cache_set(keywords, data, 60 * 60 * 24)
        claims = data.get("claims", [])
    unique_claims = list({c["text"]: c for c in claims}.values())
    for i, claim in enumerate(unique_claims):
        unique_claims[i]["count"] = claims.count(claim)
    unique_claims = sorted(
        unique_claims, key=lambda c: c.get("claimDate", "1970"), reverse=True
    )
    unique_claims = sorted(unique_claims, key=lambda c: c["count"], reverse=True)
    for i, claim in enumerate(unique_claims):
        unique_claims[i]["id"] = i
    unique_claims = [
        c
        for c in unique_claims
        if c.get("claimReview") and c["claimReview"][0].get("reviewDate")
    ]
    cache_set(cache_key, unique_claims, 60 * 60 * 24)
    return JsonResponse({"claims": unique_claims})
