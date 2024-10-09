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
