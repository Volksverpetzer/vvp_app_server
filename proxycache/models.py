from django.db import models

# Create your models here.


class TiktokToken(models.Model):
    """Model for TikTok Token Storage."""

    token = models.CharField(max_length=1000)
    refresh_token = models.CharField(max_length=1000)
    expires_in = models.IntegerField()
    date = models.DateTimeField(auto_now=True)


class InstaToken(models.Model):
    """Model for Instagram Token Storage. Multiple rows per account may
    exist; the most recently updated one is the active token."""

    token = models.CharField(max_length=1000)
    expires_in = models.IntegerField()
    date = models.DateTimeField(auto_now=True)
    account = models.CharField(max_length=100, default="volksverpetzer", db_index=True)
