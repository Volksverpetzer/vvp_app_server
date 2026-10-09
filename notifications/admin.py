from django.contrib import admin

from notifications.models import NotificationDevice


@admin.register(NotificationDevice)
class NotificationDeviceAdmin(admin.ModelAdmin):
    """Inspect registered push devices, e.g. how many are on each platform or
    build, or whether a given token has registered."""

    list_display = (
        "expo_token",
        "platform",
        "app_build",
        "notification_new_post",
        "notification_new_fact_check",
        "notification_new_pruefpunkt",
        "date",
    )
    list_filter = (
        "platform",
        "app_build",
        "notification_new_post",
        "notification_new_fact_check",
        "notification_new_pruefpunkt",
    )
    # Facet counts next to each filter option give the per-platform/-build
    # device numbers without a separate report.
    show_facets = admin.ShowFacets.ALWAYS
    search_fields = ("expo_token",)
    ordering = ("-date",)

    # View only: devices are managed by the app through /register, and
    # deleting one would silently stop pushes to that user (and cascade to
    # its PushMessageLog rows).
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
