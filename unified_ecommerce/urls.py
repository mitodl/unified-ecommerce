"""
URL configuration for unified_ecommerce project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
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
# ruff: noqa: RUF005

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("hijack/", include("hijack.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Optional UI:
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # OAuth2 Paths
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # App Paths
    re_path(r"^api/v0/meta/", include("system_meta.urls")),
    # Private Paths
    re_path(r"^_/v0/meta/", include("system_meta.private_urls")),
    re_path(r"^api/v0/payments/", include("payments.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar  # pylint: disable=wrong-import-position, wrong-import-order

    urlpatterns += [re_path(r"^__debug__/", include(debug_toolbar.urls))]
