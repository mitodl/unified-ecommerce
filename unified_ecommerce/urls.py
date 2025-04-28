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
from django.http import HttpResponse
from django.urls import include, path, re_path
from mitol.apigateway.views import ApiGatewayLogoutView

from unified_ecommerce.utils import prefix_url_patterns

base_urlpatterns = [
    path("", include("cart.urls")),
    path("auth/", include("django.contrib.auth.urls")),
    path("admin/", admin.site.urls),
    path("hijack/", include("hijack.urls")),
    # OAuth2 Paths
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # App Paths
    re_path(r"", include("openapi.urls")),
    # Private Paths
    re_path(
        r"^_/v0/booted/",
        lambda request: HttpResponse("ok", content_type="text/plain"),  # noqa: ARG005
    ),
    re_path(r"^_/v0/meta/", include("system_meta.private_urls")),
    # API Paths
    re_path(r"", include("payments.urls")),
    re_path(r"", include("system_meta.urls")),
    re_path(r"", include("users.urls")),
    re_path(r"", include("refunds.urls")),
    path("", include("mitol.google_sheets.urls")),
    re_path(
        r"",
        lambda request: HttpResponse(  # noqa: ARG005
            '<html><head><meta name="google-site-verification" content="'
            f'{settings.GOOGLE_DOMAIN_VERIFICATION_TAG_VALUE}" /></head></html>'
        ),
    ),
    path("logout/", ApiGatewayLogoutView.as_view(), name="logout"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar  # pylint: disable=wrong-import-position, wrong-import-order

    base_urlpatterns += [re_path(r"^__debug__/", include(debug_toolbar.urls))]

urlpatterns = prefix_url_patterns(base_urlpatterns)
