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
from unified_ecommerce.plugin_manager import get_plugin_manager
from unified_ecommerce.utils import redirect_with_user_message

log = logging.getLogger(__name__)
pm = get_plugin_manager()


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
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
class CheckoutCallbackView(View):
    """
    Handles the redirect from the payment gateway after the user has completed
    checkout. This may not always happen as the redirect back to the app
    occasionally fails. If it does, then the payment gateway should trigger
    things via the backoffice webhook.
    """

    def post_checkout_redirect(self, order_state, request):
        """
        Redirect the user with a message depending on the provided state.

        Args:
            - order_state (str): the order state to consider
            - order (Order): the order itself
            - request (HttpRequest): the request

        Returns: HttpResponse
        """
        if order_state == Order.STATE.CANCELED:
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_CANCELLED}
            )
        elif order_state == Order.STATE.ERRORED:
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_ERROR}
            )
        elif order_state == Order.STATE.DECLINED:
            return redirect_with_user_message(
                reverse("cart"), {"type": USER_MSG_TYPE_PAYMENT_DECLINED}
            )
        elif order_state == Order.STATE.FULFILLED:
            return redirect_with_user_message(
                reverse("cart"),
                {
                    "type": USER_MSG_TYPE_PAYMENT_ACCEPTED,
                },
            )
        else:
            if not PaymentGateway.validate_processor_response(
                settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
            ):
                log.info("Could not validate payment response for order")
            else:
                processor_response = PaymentGateway.get_formatted_response(
                    settings.ECOMMERCE_DEFAULT_PAYMENT_GATEWAY, request
                )
            log.error(
                (
                    "Checkout callback unknown error for transaction_id %s, state"
                    " %s, reason_code %s, message %s, and ProcessorResponse %s"
                ),
                processor_response.transaction_id,
                order_state,
                processor_response.response_code,
                processor_response.message,
                processor_response,
            )
            return redirect_with_user_message(
                reverse("cart"),
                {"type": USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN},
            )

    def post(self, request):
        """
        Handle successfully completed transactions.

        This does a handful of things:
        1. Verifies the incoming payload, which should be signed by the
        processor
        2. Finds and fulfills the order in the system (which should also then
        clear out the stored basket)
        3. Perform any enrollments, account status changes, etc.
        """

        with transaction.atomic():
            order = api.get_order_from_cybersource_payment_response(request)
            if order is None:
                return HttpResponse("Order not found")

            # Only process the response if the database record in pending status
            # If it is, then we can process the response as per usual.
            # If it isn't, then we just need to redirect the user with the
            # proper message.

            if order.state == Order.STATE.PENDING:
                processed_order_state = api.process_cybersource_payment_response(
                    request, order
                )
                pm.hook.post_sale(order_id=order.id, source=POST_SALE_SOURCE_REDIRECT)

                return self.post_checkout_redirect(processed_order_state, request)
            else:
                return self.post_checkout_redirect(order.state, request)


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
            {"checkout_payload": checkout_payload, "form": checkout_payload["payload"]},
        )
