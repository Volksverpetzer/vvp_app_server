from typing import Iterable

from django.conf import settings
from django.contrib import admin, messages
from django.core.cache import caches
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.translation import gettext_lazy as _

from proxycache.models import InstaToken


@admin.register(InstaToken)
class InstaTokenAdmin(admin.ModelAdmin):
    """Manage stored Instagram tokens (e.g. delete a stale token so the
    env token of the account is picked up again)."""

    list_display = ("account", "date", "expires_in")
    list_filter = ("account",)
    ordering = ("-date",)
    # Tokens are secrets: allow inspection of metadata and deletion, but keep
    # the token value itself out of the admin.
    exclude = ("token",)
    readonly_fields = ("account", "expires_in", "date")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # View and delete only: saving would bump the auto_now date field and
        # artificially extend the token's computed validity.
        return False


def _cache_aliases() -> Iterable[str]:
    """Return cache aliases configured for the project."""
    return settings.CACHES.keys()


def clear_cache_view(request: HttpRequest) -> HttpResponse:
    """Render confirmation prompt and clear configured caches on POST."""
    if not request.user.is_superuser:
        return HttpResponse(status=403)
    if request.method == "POST":
        cleared_aliases = []
        for alias in _cache_aliases():
            caches[alias].clear()
            cleared_aliases.append(alias)
        messages.success(
            request,
            _("Cleared caches: %(aliases)s.") % {"aliases": ", ".join(cleared_aliases)},
        )
        return redirect("admin:index")

    context = {
        **admin.site.each_context(request),
        "title": _("Clear Cache"),
        "cache_aliases": list(_cache_aliases()),
    }
    return TemplateResponse(request, "admin/clear_cache.html", context)


def _get_admin_urls():
    """Register custom admin URLs while preserving Django's defaults."""
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path(
                "system/clear-cache/",
                admin.site.admin_view(clear_cache_view),
                name="clear-cache",
            ),
        ]
        return custom_urls + original_get_urls()

    return get_urls


if not getattr(admin.site.get_urls, "_vvp_patched", False):
    admin.site.get_urls = _get_admin_urls()
    admin.site.get_urls._vvp_patched = True
