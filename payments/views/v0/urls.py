"""Routes specific to this version of the payments API."""
from payments.views.v0.views import BasketItemViewSet, BasketViewSet
from unified_ecommerce.routers import SimpleRouterWithNesting

router = SimpleRouterWithNesting()


basket_router = router.register(r"baskets", BasketViewSet, basename="basket")
basket_router.register(
    r"items",
    BasketItemViewSet,
    basename="basket-items",
    parents_query_lookups=["basket"],
)
