"""Views for the cart app."""

import logging

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView, View
from mitol.payment_gateway.api import PaymentGateway

from payments import api
from payments.models import Basket, Order
from system_meta.models import Product
from unified_ecommerce.constants import (
    POST_SALE_SOURCE_REDIRECT,
    USER_MSG_TYPE_PAYMENT_ACCEPTED,
    USER_MSG_TYPE_PAYMENT_CANCELLED,
    USER_MSG_TYPE_PAYMENT_DECLINED,
    USER_MSG_TYPE_PAYMENT_ERROR,
    USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN,
)
from unified_ecommerce.utils import redirect_with_user_message

log = logging.getLogger(__name__)


class CartView(LoginRequiredMixin, TemplateView):
    """View for the cart page."""

    template_name = "cart.html"
    extra_context = {"title": "Cart", "innertitle": "Cart"}

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the cart page."""
        basket = Basket.establish_basket(request)
        products = Product.objects.all()

        if not request.user.is_authenticated:
            msg = "User is not authenticated"
            raise ValueError(msg)

        return render(
            request,
            self.template_name,
            {
                **self.extra_context,
                "user": request.user,
                "basket": basket,
                "basket_items": basket.basket_items.all(),
                "products": products,
                "debug_mode": settings.MITOL_UE_PAYMENT_INTERSTITIAL_DEBUG,
            },
        )

class CheckoutInterstitialView(LoginRequiredMixin, TemplateView):
    """
    Redirects the user to the payment gateway.

    This is a simple page that just includes the checkout payload, renders a
    form and then submits the form so the user gets thrown to the payment
    gateway. They can then complete the payment process.
    """

    template_name = "checkout_interstitial.html"

    def get(self, request):
        """Render the checkout interstitial page."""
        try:
            checkout_payload = api.generate_checkout_payload(request)
        except ObjectDoesNotExist:
            return HttpResponse("No basket")
        if (
            "country_blocked" in checkout_payload
            or "no_checkout" in checkout_payload
            or "purchased_same_courserun" in checkout_payload
            or "purchased_non_upgradeable_courserun" in checkout_payload
            or "invalid_discounts" in checkout_payload
        ):
            return checkout_payload["response"]

        return render(
            request,
            self.template_name,
            {
                "checkout_payload": checkout_payload,
                "form": checkout_payload["payload"],
                "debug_mode": settings.MITOL_UE_PAYMENT_INTERSTITIAL_DEBUG,
            },
        )
