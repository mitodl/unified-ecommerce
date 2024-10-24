"""Routes specific to this version of the payments API."""

from django.urls import include, path, re_path

from payments.views.v0 import (
    BackofficeCallbackView,
    BasketViewSet,
    CheckoutApiViewSet,
    CheckoutCallbackView,
    OrderHistoryViewSet,
    clear_basket,
    create_basket_from_product,
)
from unified_ecommerce.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()

basket_router = router.register(r"baskets", BasketViewSet, basename="basket")

router.register(r"orders/history", OrderHistoryViewSet, basename="orderhistory_api")

router.register(
    r"checkout/<str:system_slug>", CheckoutApiViewSet, basename="checkout"
)

urlpatterns = [
    path(
        "baskets/create_from_product/<str:system_slug>/<str:sku>/",
        create_basket_from_product,
        name="create_from_product",
    ),
    path(
        "baskets/clear/<str:system_slug>/",
        clear_basket,
        name="clear_basket",
    ),
    path(
        "checkout/callback/",
        BackofficeCallbackView.as_view(),
        name="checkout-callback",
    ),
    re_path("^", include(router.urls)),
    path(
        "checkout/result/",
        CheckoutCallbackView.as_view(),
        name="checkout-result-callback",
    ),
]
