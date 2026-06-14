from django.urls import path

from . import views

urlpatterns = [path("info", views.info, name="info"), path("", views.info, name="root")]
