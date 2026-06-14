import uuid

from django.db import models

# Create your models here.


class FakeReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    description = models.TextField(default=None)
    url = models.URLField(default=None)
    more_info = models.TextField(default=None)
    token = models.CharField(max_length=100, default=None, null=True)
    allowed_public = models.BooleanField(default=False, null=True)
    post_id = models.CharField(max_length=100, default=None, null=True)
    date = models.DateTimeField(auto_now_add=True, null=True)
    # img = models.ImageField(upload_to='images/', default=None)
