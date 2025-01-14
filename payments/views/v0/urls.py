"""Routes specific to this version of the payments API."""

from django.urls import include, path, re_path

from payments.views.v0 import (
    BackofficeCallbackView,
    BasketViewSet,
    CheckoutCallbackView,
    DiscountAPIViewSet,
    OrderHistoryViewSet,
    add_discount_to_basket,
    clear_basket,
    create_basket_from_product,
    create_basket_with_products,
    get_user_basket_for_system,
    start_checkout,
)
from unified_ecommerce.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()

basket_router = router.register(r"baskets", BasketViewSet, basename="basket")

router.register(r"orders/history", OrderHistoryViewSet, basename="orderhistory_api")

urlpatterns = [
    path(
        "baskets/for_system/<str:system_slug>/",
        get_user_basket_for_system,
        name="get_user_basket_for_system",
    ),
    path(
        "baskets/create_from_product/<str:system_slug>/<str:sku>/<str:discount_code>/",
        create_basket_from_product,
        name="create_from_product",
    ),
    path(
        "baskets/create_with_products/",
        create_basket_with_products,
        name="create_with_products",
    ),
    path(
        "baskets/clear/<str:system_slug>/",
        clear_basket,
        name="clear_basket",
    ),
    path(
        "baskets/add_discount/<str:system_slug>/",
        add_discount_to_basket,
        name="add_discount",
    ),
    path(
        "checkout/callback/",
        BackofficeCallbackView.as_view(),
        name="checkout-callback",
    ),
    path(
        "checkout/result/",
        CheckoutCallbackView.as_view(),
        name="checkout-result-callback",
    ),
    path(
        "checkout/<str:system_slug>/",
        start_checkout,
        name="start_checkout",
    ),
    path(
        "discounts/",
        DiscountAPIViewSet.as_view(),
        name="discount-api",
    ),
    re_path(
        r"^",
        include(
            router.urls,
        ),
    ),
]
