import uuid

from django.db import models


class ContactRequest(models.Model):
    """A generic contact request submitted from the app."""

    class Category(models.TextChoices):
        REPORT_FAKE = "report_fake", "Fake melden"
        APP_FEEDBACK = "app_feedback", "App-Feedback"
        OTHER = "other", "Sonstiges"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=20, choices=Category.choices)
    # Title of the request; for report_fake this holds the reported URL.
    title = models.CharField(max_length=500)
    message = models.TextField()
    # Client metadata for triage (e.g. "Volksverpetzer", "2.3.0", "ios").
    app_variant = models.CharField(max_length=100, default="", blank=True)
    app_version = models.CharField(max_length=50, default="", blank=True)
    platform = models.CharField(max_length=50, default="", blank=True)
    date = models.DateTimeField(auto_now_add=True, null=True)
