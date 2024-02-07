"""Routes specific to this version of the payments API."""
from django.urls import include, path, re_path

from payments.views.v0 import (
    BasketItemViewSet,
    BasketViewSet,
    clear_basket,
    create_basket_from_product,
)
from unified_ecommerce.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()

basket_router = router.register(r"baskets", BasketViewSet, basename="basket")
basket_router.register(
    r"items",
    BasketItemViewSet,
    basename="basket-items",
    parents_query_lookups=["basket"],
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
    re_path("^", include(router.urls)),
]
