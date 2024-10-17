"""Routes for the cart app."""

from django.urls import path

from cart.views import CartView, CheckoutInterstitialView

urlpatterns = [
    path(
        "checkout/to_payment/<str:system_slug>/",
        CheckoutInterstitialView.as_view(),
        name="checkout_interstitial_page",
    ),
    path("cart/<str:system_slug>/", CartView.as_view(), name="cart"),
]
