# Urls Routing Django
from django.urls import path

from . import views

urlpatterns = [
    path("paymentIntent", views.paymentIntent, name="paymentIntent"),
]
