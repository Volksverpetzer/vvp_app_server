# views for monitoring push receipt statuses
import json

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpRequest
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from notifications.helper import check_receipts
from notifications.models import PushMessageLog


@login_required
def receipts_monitor(request: HttpRequest):
    """
    View to check push receipt statuses for messages sent in the last 24 hours.
    """
    last_24 = timezone.now() - timedelta(days=1)
    qs = PushMessageLog.objects.filter(date__gt=last_24)
    paginator = Paginator(qs, 500)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    raw_errors = check_receipts(page_obj.object_list)
    errors = []
    for err in raw_errors:
        err_dict = err.__dict__.copy()
        errors.append(
            {
                "id": getattr(err, "id", err_dict.get("id")),
                "status": getattr(err, "status", err_dict.get("status")),
                "details": json.dumps(err_dict),
            }
        )

    context = {
        "page_obj": page_obj,
        "errors": errors,
    }
    return render(request, "receipts_monitor.html", context)
