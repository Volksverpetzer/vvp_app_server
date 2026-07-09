from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.core.paginator import Paginator
from django.utils import timezone

from notifications.helper import check_receipts
from notifications.models import PushMessageLog


class Command(BaseCommand):
    def handle(self, *args: Any, **options: Any) -> None:
        qs = PushMessageLog.objects.filter(date__gt=timezone.now() - timedelta(days=1))
        paginator = Paginator(qs, 500)
        for page in paginator.page_range:
            messages = [message for message in paginator.page(page).object_list]
            check_receipts(messages)
