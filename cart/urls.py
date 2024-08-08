"""Routes for the cart app."""

from django.urls import path

from cart.views import CartView, CheckoutCallbackView, CheckoutInterstitialView

urlpatterns = [
    path(
        r"checkout/result/",
        CheckoutCallbackView.as_view(),
        name="checkout-result-callback",
    ),
    path(
        "checkout/to_payment",
        CheckoutInterstitialView.as_view(),
        name="checkout_interstitial_page",
    ),
    path("", CartView.as_view(), name="cart"),
]
