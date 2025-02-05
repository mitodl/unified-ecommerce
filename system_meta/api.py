"""API functions for system metadata."""

import logging

import requests
from django.conf import settings
from reversion import create_revision

from system_meta.models import Product
from unified_ecommerce.utils import parse_readable_id

log = logging.getLogger(__name__)


def get_product_metadata(
    platform: str, readable_id: str, *, all_data: bool = False
) -> dict | None:
    """
    Get product metadata from the Learn API.

    Args:
        platform: The platform slug.
        readable_id: The readable ID of the product.
        all_data: Whether to return all the data returned or the minimal amount
                  to bootstrap a product.

    Returns:
        The product metadata from the Learn API.
    """

    def _format_output(data: dict, *, all_data: bool) -> dict:
        """Format the Learn API data accordingly."""

        if all_data:
            return data.get("results", [])[0]

        course_data = data.get("results")[0]
        image_data = course_data.get("image", {})
        url = course_data.get("url", "")
        prices = course_data.get("prices", [])
        prices.sort()
        price = prices[-1] if len(prices) else 0

        runs = course_data.get("runs", [])
        run = next((r for r in runs if r.get("run_id") == readable_id), None)
        if run:
            run_prices = run.get("prices", [])
            run_prices.sort()
            run_price = run_prices[-1] if len(run_prices) else 0

        return {
            "sku": run.get("run_id") if run else course_data.get("readable_id"),
            "title": course_data.get("title"),
            "description": course_data.get("description"),
            "image": {
                "image_url": image_data.get("url"),
                "alt_text": image_data.get("alt"),
                "description": image_data.get("description"),
            }
            if image_data
            else None,
            "price": run_price if run and run_price > price else price,
            "url": url if url else "",
        }

    try:
        split_readable_id, split_run = parse_readable_id(readable_id)
        response = requests.get(
            f"{settings.MITOL_LEARN_API_URL}learning_resources/",
            params={"platform": platform, "readable_id": split_readable_id},
            timeout=10,
        )
        response.raise_for_status()
        raw_response = response.json()

        if raw_response.get("count", 0) > 0:
            course_data = raw_response.get("results")[0]
            if split_run and course_data.get("runs"):
                test_run = next(
                    (
                        r
                        for r in course_data.get("runs")
                        if r.get("run_id") == readable_id
                    ),
                    None,
                )
                if test_run:
                    return _format_output(raw_response, all_data=all_data)

                return None

            return _format_output(raw_response, all_data=all_data)
        else:
            return None
    except requests.RequestException:
        log.exception("Failed to get product metadata for %s", readable_id)
        return None


def update_product_metadata(product_id: int) -> None:
    """Get product metadata from the Learn API."""

    try:
        with create_revision():
            product = Product.objects.get(id=product_id)
            fetched_metadata = get_product_metadata(product.system.slug, product.sku)

            if not fetched_metadata:
                log.warning("No Learn results found for product %s", product)
                return

            product.image_metadata = (
                fetched_metadata.get("image", None) or product.image_metadata
            )

            product.name = fetched_metadata.get("title", product.name)
            product.description = fetched_metadata.get(
                "description", product.description
            )
            product.price = fetched_metadata.get("price", product.price)
            product.details_url = fetched_metadata.get("url", product.details_url)

            product.save()
    except requests.RequestException:
        log.exception("Failed to update metadata for product %s", product.id)
