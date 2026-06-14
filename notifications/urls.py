from django.urls import path

from .services.receipts_monitor import receipts_monitor
from .services.register import register
from .services.task_monitor import task_monitor
from .services.webhook_new_post import webhook_new_post
from .services.notification_stats import notification_stats

urlpatterns = [
    path("register", register, name="register"),
    path("webhook_new_post", webhook_new_post, name="webhook_new_post"),
    path("notification_stats", notification_stats, name="notification_stats"),
    path("task_monitor", task_monitor, name="task_monitor"),
    path("receipts_monitor", receipts_monitor, name="receipts_monitor"),
]
