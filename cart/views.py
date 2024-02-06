"""Views for the cart app."""

import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.http.request import HttpRequest
from django.shortcuts import render
from django.views.generic import TemplateView

from payments.models import Basket
from system_meta.models import IntegratedSystem, Product

log = logging.getLogger(__name__)


class CartView(LoginRequiredMixin, TemplateView):
    """View for the cart page."""

    template_name = "cart.html"
    extra_context = {"title": "Cart", "innertitle": "Cart"}

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the cart page."""
        system = IntegratedSystem.objects.first()
        basket = Basket.establish_basket(request, system)
        products = Product.objects.filter(system=system).all()

        if not request.user.is_authenticated:
            msg = "User is not authenticated"
            raise ValueError(msg)

        return render(
            request,
            self.template_name,
            {
                **self.extra_context,
                "basket": basket,
                "basket_items": basket.basket_items.all(),
                "products": products,
            },
        )
