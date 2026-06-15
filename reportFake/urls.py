from django.urls import path
from . import views

urlpatterns = [
    path("reportFake", views.reportFake, name="reportFake"),
    path("triageFake", views.triageFake, name="triageFake"),
    path("archiveFake", views.archiveFake, name="archiveFake"),
    path("assign-bluesky", views.assign_bluesky, name="assign_bluesky"),
    path("statusFake/<uuid:report_id>", views.statusFake, name="statusFake"),
]
