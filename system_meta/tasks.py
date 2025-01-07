"""Tasks for the system_meta app."""

import logging
from typing import Optional

import requests
from celery import shared_task


@shared_task
def update_products(product_id: Optional[int] = None):
    """
    Update product metadata from the Learn API.

    Updates all products if a product_id is not provided. Pulls the image metadata,
    name, and description from the Learn API. If the product has a run ID, it also
    pulls the price from the specific run; otherwise, pulls the price from the
    resource.
    """
    from system_meta.api import update_product_metadata
    from system_meta.models import Product

    log = logging.getLogger(__name__)
    if product_id:
        products = Product.objects.filter(id=product_id)
    else:
        products = Product.objects.all()

    for product in products:
        try:
            update_product_metadata(product.id)
        except requests.RequestException:
            log.exception("Failed to update metdata for product %s", product.id)
