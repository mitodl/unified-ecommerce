import logging
from typing import Optional

import requests
from celery import shared_task
from django.conf import settings


@shared_task
def update_products(product_id: Optional[int] = None):
    """
    Update all product's image metadata.  If product_id is provided, only update the
    product with that ID.  Otherwise, update all products.
    """
    from .models import Product

    log = logging.getLogger(__name__)
    if product_id:
        products = Product.objects.filter(id=product_id)
    else:
        products = Product.objects.all()
    for product in products:
        try:
            response = requests.get(
                f"{settings.MITOL_LEARN_API_URL}learning_resources/",
                params={"platform": product.system.slug, "readable_id": product.sku},
                timeout=10,
            )
            response.raise_for_status()
            results_data = response.json()
            course_data = results_data.get("results")[0]
            image_data = course_data.get("image")
            product.image_metadata = {
                "imageURL": image_data.get("url"),
                "alt_text": image_data.get("alt"),
                "description": image_data.get("description"),
            }
            product.save()
        except requests.RequestException:
            log.exception("Failed to retrieve image data for product %s", product.id)
