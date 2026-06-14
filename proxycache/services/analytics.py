import io
import logging
import os
from datetime import datetime
from typing import Optional

import geopandas as gpd
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd
import requests
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit  # type: ignore[reportMissingTypeStubs]
from shapely import LineString, MultiLineString

from vvp_app_server.cache_utils import cache_get, cache_set

logger = logging.getLogger(__name__)

# Cache TTLs: default short and fallback long
SHORT_CACHE_TTL = 60 * 5  # 5 minutes
LONG_CACHE_TTL = 60 * 60 * 24  # 1 day

DEFAULT_SITE = "volksverpetzer.de"

SITES = {
    "volksverpetzer.de": {"wp_base": "https://volksverpetzer.de"},
    "pruefpunkt.org": {"wp_base": "https://www.pruefpunkt.org"},
}


def _resolve_site(request: HttpRequest) -> tuple[str, JsonResponse | None]:
    site = request.GET.get("site", DEFAULT_SITE)
    if site not in SITES:
        return "", JsonResponse({"error": "invalid site"}, status=400)
    return site, None


# Population data for German states
REGION_MAPPING = {
    "NW": {"name": "Nordrh.-Westf.", "population": 17933000},
    "BY": {"name": "Bayern", "population": 13124000},
    "BW": {"name": "Baden-Württ.", "population": 11263000},
    "BE": {"name": "Berlin", "population": 3669500},
    "HE": {"name": "Hessen", "population": 6293000},
    "NI": {"name": "Niedersachsen", "population": 7993600},
    "HH": {"name": "Hamburg", "population": 1845200},
    "SN": {"name": "Sachsen", "population": 4077900},
    "RP": {"name": "Rheinl.-Pfalz", "population": 4093900},
    "SH": {"name": "Schlesw.-Holst.", "population": 2911000},
    "BB": {"name": "Brandenburg", "population": 2534000},
    "TH": {"name": "Thüringen", "population": 2100000},
    "ST": {"name": "Sachsen-Anh.", "population": 2173000},
    "MV": {"name": "Meckl.-Vorp.", "population": 1607000},
    "HB": {"name": "Bremen", "population": 680000},
    "SL": {"name": "Saarland", "population": 982000},
}


@require_http_methods(["GET"])
def shares(request: HttpRequest, path: Optional[str] = None) -> HttpResponse:
    # Ensure path is properly handled
    if path == "":
        path = None

    site, err = _resolve_site(request)
    if err:
        return err
    cache_key = "analytics:shares:" + request.get_full_path()
    entry = cache_get(cache_key)
    cached_data = entry.get("data") if entry else None
    headers = {"Authorization": "Bearer " + os.environ["PLAUSIBLE_TOKEN"]}
    # serve cache if fresh
    if (
        entry
        and (datetime.now() - entry["fetched_at"]).total_seconds() < SHORT_CACHE_TTL
    ):
        return JsonResponse(cached_data)
    # live fetch
    payload = {
        "site_id": site,
        "metrics": ["events"],
        "date_range": "all" if path else "7d",
        "filters": [["is", "event:name", ["Share"]]],
    }
    if path:
        clean_path = path.lstrip("/")
        payload["filters"].append(["is", "event:page", ["/" + clean_path]])
    try:
        resp = requests.post(
            "https://plausible.io/api/v2/query",
            json=payload,
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("results", [])
        result = {"events": data[0]["metrics"][0] if data else 0}
        cache_set(
            cache_key, {"data": result, "fetched_at": datetime.now()}, SHORT_CACHE_TTL
        )
        return JsonResponse(result)
    except Exception:
        if cached_data is not None:
            cache_set(
                cache_key,
                {"data": cached_data, "fetched_at": entry["fetched_at"]},
                LONG_CACHE_TTL,
            )
            return JsonResponse(cached_data)
        return HttpResponse(status=502)


@require_http_methods(["GET"])
def links(request: HttpRequest, remaining: str) -> HttpResponse:
    cache_key = "analytics:links:" + request.get_full_path()
    entry = cache_get(cache_key)
    cached_data = entry.get("data") if entry else None
    fetched_at = entry.get("fetched_at") if entry else None
    # serve cache if fresh
    if fetched_at and (datetime.now() - fetched_at).total_seconds() < SHORT_CACHE_TTL:
        return JsonResponse(cached_data)
    # live fetch
    # live fetch headers
    headers = {"Authorization": f"Bearer {os.environ.get('PLAUSIBLE_TOKEN', '')}"}
    page = f"/{remaining}/"
    try:
        # Use Plausible v2 breakdown endpoint with required period parameter
        url = "https://plausible.io/api/v2/query"
        payload = {
            "site_id": "volksverpetzer.de",
            "metrics": ["events"],
            "dimensions": ["event:props:url"],
            "date_range": "all",
            "filters": [
                ["is", "event:page", [page]],
                ["is", "event:name", ["Outbound Link: Click"]],
            ],
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        raw = resp.json().get("results", [])
        links = [
            {
                "visitors": item.get("metrics")[0],
                "url": item.get("dimensions")[0],
            }
            for item in raw
            if int(item.get("metrics")[0]) > 2
        ]
        result = {"links": links}
        cache_set(
            cache_key,
            {"data": result, "fetched_at": datetime.now()},
            SHORT_CACHE_TTL,
        )
        return JsonResponse(result)
    except Exception as e:
        logger.exception("Error in links: %s", e)
        if cached_data is not None:
            cache_set(
                cache_key,
                {"data": cached_data, "fetched_at": fetched_at},
                LONG_CACHE_TTL,
            )
            return JsonResponse(cached_data)
        return HttpResponse(status=502)


@require_http_methods(["GET"])
@ratelimit(key="ip", rate="5/m", method=["GET"], block=True)
@ratelimit(key="ip", rate="30/h", method=["GET"], block=True)
def map(request: HttpRequest):
    # Fixed key — map takes no query parameters; including the query string
    # would create separate cache entries per spurious parameter and defeat
    # the DoS mitigation entirely.
    cache_key = "analytics:map"
    entry = cache_get(cache_key)

    if entry:
        return HttpResponse(entry["data"], content_type="image/png")

    import matplotlib
    matplotlib.use("Agg")
    url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/refs/heads/main/2_bundeslaender/4_niedrig.geo.json"

    # Fetch region stats via Plausible v2 API
    bearer = f"Bearer {os.environ.get('PLAUSIBLE_TOKEN', '')}"
    headers = {"Authorization": bearer}
    payload = {
        "site_id": "volksverpetzer.de",
        "metrics": ["pageviews"],
        "date_range": "7d",
        "dimensions": ["visit:region"],
        "filters": [["is", "visit:country", ["DE"]]],
    }
    try:
        geo_resp = requests.get(url, timeout=15)
        geo_resp.raise_for_status()
        germany = gpd.read_file(io.BytesIO(geo_resp.content))
        resp = requests.post(
            "https://plausible.io/api/v2/query",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            raise ValueError("bad status")
        results = resp.json().get("results", [])

        # Process data and normalize by population - match regions function logic
        processed_data = []
        for r in results:
            region_code = r["dimensions"][0]
            parts = region_code.split("-")
            key = parts[1] if len(parts) > 1 else region_code
            pageviews = r["metrics"][0]

            # Get population data for normalization
            region_info = REGION_MAPPING.get(key, {"population": 1})
            # Normalize pageviews per 100,000 population (same formula as convert_to_csv)
            normalized_pageviews = pageviews / (region_info["population"] / 10**5)

            processed_data.append(
                {
                    "region": key,
                    "pageviews": pageviews,
                    "normalized_pageviews": normalized_pageviews,
                }
            )

        data = pd.DataFrame(processed_data)
        germany["id"] = germany["id"].astype(str).str.split("-").str[1]
        germany = germany.merge(data, left_on="id", right_on="region", how="left")

        # Use normalized pageviews for quartile calculation instead of raw pageviews
        germany["quartile"] = pd.qcut(
            germany["normalized_pageviews"], 4, labels=False, duplicates="drop"
        )

        colors = ["#D31C74", "#DB2685", "#3893c0", "#1b7194"]
        colors.reverse()
        cmap = mcolors.ListedColormap(colors)
        fig, ax = plt.subplots(figsize=(10, 10))
        ax.set_facecolor("black")
        fig.set_facecolor("#1b7194")
        ax.axis("off")
        boundary = germany.union_all().buffer(0.03).simplify(0.03).boundary
        if isinstance(boundary, LineString):
            lines = [boundary]
        elif isinstance(boundary, MultiLineString):
            lines = list(boundary.geoms)
        else:
            lines = []
        lines.sort(key=lambda line: line.length, reverse=True)
        for line in lines[:1]:
            ax.plot(*line.xy, color="white", linewidth=18, zorder=2)
        germany.plot(
            column="quartile",
            cmap=cmap,
            linewidth=0.5,
            ax=ax,
            edgecolor="white",
            zorder=3,
        )
        img_io = io.BytesIO()
        plt.savefig(
            img_io,
            format="png",
            bbox_inches="tight",
            pad_inches=0,
            facecolor=fig.get_facecolor(),
        )
        plt.close(fig)
        img_io.seek(0)
        img_data = img_io.getvalue()

        cache_set(cache_key, {"data": img_data}, 60 * 60)  # 1 hour

        return HttpResponse(img_data, content_type="image/png")
    except Exception as e:
        logger.exception("Error in map: %s", e)
        return HttpResponse(status=502)


@require_http_methods(["GET"])
def script(request: HttpRequest, extension: str = "js") -> HttpResponse:
    """Proxy /js/script.js, caching plausible.io script"""
    resp = requests.get(
        f"https://plausible.io/js/plausible.{extension}",
        timeout=10,
    )
    response = HttpResponse(
        resp.content,
        content_type=resp.headers.get("Content-Type", "application/javascript"),
    )
    response["Cache-Control"] = "public, s-maxage=600000"
    return response


def get_delta(page: str, site: str = DEFAULT_SITE):
    if site not in SITES:
        logger.error("get_delta called with unknown site: %s", site)
        return 0
    try:
        slug = page.strip("/").split("/")[-1]
        wp_base = SITES[site]["wp_base"]
        wpresp = requests.get(
            f"{wp_base}/wp-json/wp/v2/posts?slug={slug}",
            headers={"User-Agent": "vvp_app_server"},
            timeout=10,
        )
        # Check if response is valid before attempting to parse JSON
        if wpresp.status_code != 200:
            logger.warning(
                f"WordPress API returned status code {wpresp.status_code} for slug {slug}"
            )
            return 0

        # Check if response content is not empty
        if not wpresp.text.strip():
            logger.warning(f"WordPress API returned empty response for slug {slug}")
            return 0

        # Now try to parse JSON with proper error handling
        try:
            wpdata = wpresp.json()
            if wpdata and isinstance(wpdata, list) and len(wpdata) > 0:
                date = wpdata[0]["date_gmt"]
                timestamp = pd.to_datetime(date, utc=True).timestamp()
                return int((pd.Timestamp.now(tz="UTC").timestamp() - timestamp) / 50)
            else:
                logger.warning(
                    f"WordPress API returned empty data array for slug {slug}"
                )
        except requests.exceptions.JSONDecodeError as json_err:
            logger.error(
                f"JSON decode error for response: {wpresp.text[:100]}... (truncated)"
            )
            raise json_err
    except Exception as e:
        logger.exception("Error in get_delta: %s", e)
    return 0


@require_http_methods(["GET"])
def stats(request: HttpRequest, remaining: str) -> JsonResponse | HttpResponse:
    """Endpoint /stats/<category>/<slug>/ with dynamic TTL"""
    site, err = _resolve_site(request)
    if err:
        return err
    page = f"/{remaining}/"
    cache_key = "analytics:stats:" + request.get_full_path()
    entry = cache_get(cache_key)
    cached = entry.get("data") if entry else None
    date_delta = get_delta(page, site)
    headers = {"Authorization": "Bearer " + os.environ["PLAUSIBLE_TOKEN"]}
    payload = {
        "site_id": site,
        "metrics": ["pageviews"],
        "date_range": "all",
        "filters": [["is", "event:page", [page]]],
    }
    try:
        resp = requests.post(
            "https://plausible.io/api/v2/query",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            raise ValueError("bad status")
        data = resp.json()
        results = data.get("results", [])
        pageviews = results[0]["metrics"][0] if results else 0
        result = {"pageviews": pageviews}
        cache_set(
            cache_key,
            {"data": result, "fetched_at": datetime.now()},
            60 * 30 + date_delta,
        )
        return JsonResponse(result)
    except Exception as e:
        logger.exception("Error in stats: %s", e)
        if cached is not None:
            return JsonResponse(cached)
        return HttpResponse(status=502)


@require_http_methods(["GET"])
def faves(request: HttpRequest, remaining: str) -> JsonResponse | HttpResponse:
    """Endpoint /favs/<category>/<slug>/ for Fav events"""
    site, err = _resolve_site(request)
    if err:
        return err
    cache_key = "analytics:faves:" + request.get_full_path()
    entry = cache_get(cache_key)
    cached = entry.get("data") if entry else None
    headers = {"Authorization": "Bearer " + os.environ["PLAUSIBLE_TOKEN"]}
    page = f"/{remaining}/"
    payload = {
        "site_id": site,
        "metrics": ["events"],
        "date_range": "all",
        "filters": [["is", "event:name", ["favorite"]], ["is", "event:page", [page]]],
    }
    try:
        resp = requests.post(
            "https://plausible.io/api/v2/query",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            raise ValueError("bad status")
        data = resp.json()
        results = data.get("results", [])
        events = results[0]["metrics"][0] if results else 0
        result = {"events": events}
        cache_set(
            cache_key, {"data": result, "fetched_at": datetime.now()}, 60 * 60 * 24
        )
        return JsonResponse(result)
    except Exception as e:
        logger.exception("Error in faves: %s", e)
        if cached is not None:
            return JsonResponse(cached)
        return HttpResponse(status=502)


@require_http_methods(["GET"])
def regions(request: HttpRequest) -> JsonResponse | HttpResponse:
    """Endpoint /api/regions returning CSV"""
    cache_key = "analytics:regions:" + request.get_full_path()
    entry = cache_get(cache_key)
    cached = entry.get("data") if entry else None
    headers = {"Authorization": "Bearer " + os.environ["PLAUSIBLE_TOKEN"]}
    payload = {
        "site_id": "volksverpetzer.de",
        "metrics": ["pageviews"],
        "date_range": "7d",
        "dimensions": ["visit:region"],
        "filters": [["is", "visit:country", ["DE"]]],
    }
    try:
        resp = requests.post(
            "https://plausible.io/api/v2/query",
            json=payload,
            headers=headers,
            timeout=10,
        )
        if resp.status_code != 200:
            raise ValueError("bad status")
        v2data = resp.json().get("results", [])
        data = [
            {"region": r["dimensions"][0], "pageviews": r["metrics"][0]} for r in v2data
        ]
        csv = convert_to_csv(data)
        result = csv
        cache_set(
            cache_key, {"data": result, "fetched_at": datetime.now()}, 60 * 60 * 24
        )
        response = HttpResponse(result, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="region-stats.csv"'
        return response
    except Exception as e:
        logger.exception("Error in regions: %s", e)
        if cached is not None:
            response = HttpResponse(cached, content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="region-stats.csv"'
            return response
        return HttpResponse(status=502)


def convert_to_csv(jsonData: list[dict[str, int]]) -> str:
    headers = ["region", "name", "pageviews"]
    rows = []
    for item in jsonData:
        reg = str(item.get("region", ""))
        parts = reg.split("-")
        key = parts[1] if len(parts) > 1 else reg
        region = REGION_MAPPING.get(key, {"name": reg, "population": 1})
        pv = item.get("pageviews", 0) / (region["population"] / 10**5)
        rows.append(f"{reg.replace('-', '.')},{region['name']},{pv}")
    return "\n".join([",".join(headers)] + rows)
