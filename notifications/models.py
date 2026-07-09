from django.db import models

# Create your models here.


class NotificationDevice(models.Model):
    expo_token = models.CharField(max_length=256, unique=True)
    notification_new_post = models.BooleanField(default=True)
    notification_new_fact_check = models.BooleanField(default=True)
    notification_new_pruefpunkt = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

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
