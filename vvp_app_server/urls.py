"""vvp_app_server URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from proxycache.services.tiktok_feed import tiktokFeed

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("notifications.urls")),
    path("", include("factApi.urls")),
    # Legacy, only used by old app versions; superseded by the contact app.
    path("", include("reportFake.urls")),
    path("", include("contact.urls")),
    path("", include("info.urls")),
    path("", include("payment.urls")),
    path("proxy/", include("proxycache.urls")),
    path("tiktok/tiktokFeed", tiktokFeed, name="tiktokFeed"),
    path("accounts/", include("django.contrib.auth.urls")),
]
