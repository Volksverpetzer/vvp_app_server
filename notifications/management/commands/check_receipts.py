from typing import Any

from django.core.management.base import BaseCommand

from notifications.helper import process_receipts


class Command(BaseCommand):
    help = "Check pending push receipts and delete unregistered devices."

    def handle(self, *args: Any, **options: Any) -> None:
        removed = process_receipts()
        self.stdout.write(f"Removed {removed} unregistered device(s)")
