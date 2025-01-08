"""API functions for system metadata."""

import logging

import requests
from django.conf import settings

from system_meta.models import Product
from unified_ecommerce.utils import parse_readable_id

log = logging.getLogger(__name__)


def update_product_metadata(product_id: int) -> None:
    """Get product metadata from the Learn API."""

    try:
        product = Product.objects.get(id=product_id)
        resource, run = parse_readable_id(product.sku)
        response = requests.get(
            f"{settings.MITOL_LEARN_API_URL}learning_resources/",
            params={"platform": product.system.slug, "readable_id": resource},
            timeout=10,
        )
        response.raise_for_status()
        results_data = response.json()

        if results_data.get("count", 0) == 0:
            log.warning("No Learn results found for product %s", product)
            return

        course_data = results_data.get("results")[0]

        image_data = course_data.get("image")
        product.image_metadata = (
            {
                "image_url": image_data.get("url"),
                "alt_text": image_data.get("alt"),
                "description": image_data.get("description"),
            }
            if image_data
            else product.image_metadata
        )

        product.name = course_data.get("title", product.name)
        product.description = course_data.get("description", product.description)

        # If there are runs, we'll overwrite this with the run's price later.
        product_prices = course_data.get("prices", [])
        product_prices.sort()
        product.price = product_prices[-1] if len(product_prices) else product.price

        runs = course_data.get("runs")
        if runs:
            run = next((r for r in runs if r.get("readable_id") == product.sku), None)
            if run:
                product_prices = run.get("prices", [])
                product_prices.sort()
                product.price = (
                    product_prices[-1] if len(product_prices) else product.price
                )

        product.save()
    except requests.RequestException:
        log.exception("Failed to update metadata for product %s", product.id)
