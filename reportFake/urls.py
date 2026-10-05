from django.urls import path
from . import views

urlpatterns = [
    path("reportFake", views.reportFake, name="reportFake"),
    path("statusFake/<uuid:report_id>", views.statusFake, name="statusFake"),
]
