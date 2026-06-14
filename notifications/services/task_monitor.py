# views.py
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django_q.models import OrmQ, Schedule, Task  # type: ignore[reportMissingTypeStubs]
from django_q.status import Stat, get_broker  # type: ignore[reportMissingTypeStubs]


@login_required
def task_monitor(request: HttpRequest) -> HttpResponse:
    """
    View to display the current status of all tasks in Q Cluster
    """
    # Get task statistics
    broker = get_broker("default")
    stats = Stat.get_all(broker=broker)

    # Get clusters status
    clusters = []
    for stat in stats:
        clusters.append(
            {
                "id": stat.cluster_id,
                "status": stat.status,
                "ping": stat.ping,
                "workers": stat.workers,
                "uptime": timezone.now() - stat.tob if stat.tob else None,
                "successful": stat.done,
                "failed": stat.errored,
            }
        )

    # Get tasks from the last 7 days
    last_7_days = timezone.now() - timedelta(hours=24 * 7)
    recent_tasks = Task.objects.filter(started__gte=last_7_days).order_by("-started")

    # Get failed tasks with error information
    failed_tasks = Task.objects.filter(
        success=False, stopped__isnull=False, started__gte=last_7_days
    ).order_by("-stopped")

    # Get tasks by status counts
    task_counts = {
        "success": Task.objects.filter(success=True, started__gte=last_7_days).count(),
        "failed": Task.objects.filter(
            success=False, stopped__isnull=False, started__gte=last_7_days
        ).count(),
        "queued": OrmQ.objects.count(),
        "in_progress": Task.objects.filter(
            started__isnull=False, stopped__isnull=True, started__gte=last_7_days
        ).count(),
    }

    # Get scheduled tasks
    scheduled_tasks = Schedule.objects.all().order_by("next_run")

    context = {
        "clusters": clusters,
        "recent_tasks": recent_tasks,
        "failed_tasks": failed_tasks,
        "task_counts": task_counts,
        "scheduled_tasks": scheduled_tasks,
    }

    return render(request, "task_monitor.html", context)
