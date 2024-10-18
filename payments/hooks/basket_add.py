"""Add to cart hook implementations for payments."""

import pluggy

hookimpl = pluggy.HookimplMarker("unified_ecommerce")


class CustomerVerificationHooks:
    """Contains hooks to verify customer information."""

    @hookimpl(wrapper=True, specname="basket_add")
    def locate_customer(self, basket_id, basket_item):
        """
        Locate the customer.

        We'll need to geolocate the customer for tax and blocked country
        determinations, so this performs this task and puts the necessary data
        in the basket.

        Args:
        basket_id (int): the ID of the basket the item is being added to
        basket_item (int): the ID of the item that will be added
        """

        return
