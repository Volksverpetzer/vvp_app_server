import uuid

from django.db import models

# Create your models here.


class FakeReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField(default=None)
    url = models.URLField(default=None)
    more_info = models.TextField(default=None)
    # Legacy nullable columns: existing rows hold NULLs, so switching to
    # blank=True/default="" would need a data migration — left as-is.
    token = models.CharField(max_length=100, default=None, null=True)  # noqa: DJ001
    allowed_public = models.BooleanField(default=False, null=True)
    post_id = models.CharField(max_length=100, default=None, null=True)  # noqa: DJ001
    # False until the report reached the Asana board (pre-Asana rows were
    # delivered by email); deduped resubmits re-attempt the post.
    posted_to_asana = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True, null=True)
    # img = models.ImageField(upload_to='images/', default=None)

    def __str__(self) -> str:
        return f"FakeReport ({self.url})"
