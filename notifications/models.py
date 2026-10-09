from django.db import models

# Create your models here.


class NotificationDevice(models.Model):
    expo_token = models.CharField(max_length=256, unique=True)
    notification_new_post = models.BooleanField(default=True)
    notification_new_fact_check = models.BooleanField(default=True)
    notification_new_pruefpunkt = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    # Client metadata sent with every registration ("os" / "version" in the
    # payload). Blank for devices that haven't re-registered since this landed.
    # db_default keeps a DB-level default so inserts from code that predates
    # these columns (old instances mid-deploy, a rollback) don't violate NOT NULL.
    platform = models.CharField(max_length=50, default="", db_default="", blank=True)
    app_build = models.CharField(max_length=50, default="", db_default="", blank=True)
    # Updated on every /register call, which the app makes on each launch while
    # notifications are allowed, so this is effectively the last app open.
    # Null for devices that haven't registered since this landed.
    last_seen = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return self.expo_token


class PushMessageLog(models.Model):
    to = models.ForeignKey(NotificationDevice, on_delete=models.CASCADE)
    body = models.CharField(max_length=256)
    title = models.CharField(max_length=256)
    data = models.JSONField()
    date = models.DateTimeField(auto_now_add=True)
    id = models.CharField(max_length=256, primary_key=True)
    checked = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.title} ({self.id})"
