"""factApi URL Views."""

from django.urls import path
from .services.google_fact import googleFact

urlpatterns = [
    path("googleFact", googleFact, name="googleFact"),
]
