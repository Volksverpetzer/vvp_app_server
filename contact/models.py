import hashlib
import json
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
    # Hash over the normalized payload; the unique constraint makes the
    # double-submit dedupe atomic (a TextField can't go into an index).
    dedupe_hash = models.CharField(max_length=64, unique=True)
    # False until the Asana task exists; deduped requests re-attempt the
    # post instead of reporting success for a task that was never created.
    posted_to_asana = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self) -> str:
        return f"{self.category}: {self.title}"

    @staticmethod
    def build_dedupe_hash(**fields: str) -> str:
        """Hash the normalized payload fields for the uniqueness check.

        JSON serialization is unambiguous, so no crafted field value can
        make two different payloads collapse to the same hash.
        """
        joined = json.dumps(fields, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(joined.encode()).hexdigest()
