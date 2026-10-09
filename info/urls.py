from django.urls import path

from . import views

urlpatterns = [
    path("info", views.info, name="info"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("", views.info, name="root"),
]
