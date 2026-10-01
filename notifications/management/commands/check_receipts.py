from typing import Any

from django.core.management.base import BaseCommand

from notifications.helper import process_receipts


class Command(BaseCommand):
    help = "Check Expo push receipts now (also runs on a schedule via Django-Q)."

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(str(process_receipts()))
