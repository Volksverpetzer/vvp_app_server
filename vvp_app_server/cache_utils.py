import json
from functools import wraps
from typing import Any, Callable, Optional

from django.core.cache import caches
from django.http import HttpRequest, JsonResponse

# Two-layer cache: fast in-memory and persistent DB
default_cache = caches["default"]
persistent_cache = caches["persistent"]


def cache_get(key: str, default: Any = None) -> Any:
    val = default_cache.get(key, default)
    if val is not None:
        return val
    val = persistent_cache.get(key, default)
    if val is not None:
        default_cache.set(key, val)
    return val


def cache_set(key: str, value: Any, timeout: Optional[int] = None) -> None:
    default_cache.set(key, value, timeout)
    persistent_cache.set(key, value, timeout)


def cache_response(key_fn: Callable[..., str], timeout: int):
    """
    Decorator for view functions that caches JSON responses.
    key_fn: a function(request, *args, **kwargs) -> cache key.
    timeout: TTL in seconds or a callable that returns TTL.
    """

    def decorator(view_func: Callable[..., JsonResponse]):
        @wraps(view_func)
        def _wrapped(request: HttpRequest, *args: Any, **kwargs: Any):
            key = key_fn(request, *args, **kwargs)
            data = cache_get(key)
            if data is not None:
                # safe=False: cached bodies may be lists (views using
                # JsonResponse(..., safe=False)), not only dicts
                resp = JsonResponse(data, safe=False)
                # edge cache: public GET with TTL
                ttl = (
                    timeout(request, *args, **kwargs) if callable(timeout) else timeout
                )
                resp["Cache-Control"] = f"public, max-age={ttl}"
                return resp
            response = view_func(request, *args, **kwargs)
            # don't cache errors: cached bodies are replayed as 200 responses
            if response.status_code != 200:
                return response
            try:
                body = json.loads(response.content)
            except Exception:
                return response
            # Determine dynamic timeout if callable
            actual_timeout = (
                timeout(request, *args, **kwargs) if callable(timeout) else timeout
            )
            cache_set(key, body, actual_timeout)
            # set edge cache header on fresh response
            if isinstance(response, JsonResponse):
                response["Cache-Control"] = f"public, max-age={actual_timeout}"
            return response

        return _wrapped

    return decorator
