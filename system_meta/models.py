"""System metadata models - integrated systems and the data surrounding them"""

import logging

import requests
import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.functional import cached_property
from mitol.common.models import TimestampedModel
from mitol.payment_gateway.payment_utils import quantize_decimal
from rest_framework_api_key.models import AbstractAPIKey
from safedelete.managers import SafeDeleteManager
from safedelete.models import SafeDeleteModel
from slugify import slugify

from unified_ecommerce.utils import SoftDeleteActiveModel

User = get_user_model()
log = logging.getLogger(__name__)


class IntegratedSystem(SafeDeleteModel, SoftDeleteActiveModel, TimestampedModel):
    """Represents an integrated system"""

    name = models.CharField(max_length=255, unique=True)
    slug = models.CharField(max_length=80, unique=True, blank=True, null=True)
    description = models.TextField(blank=True)
    api_key = models.TextField(
        blank=True,
        help_text=(
            "Shared key used by the integrated system to verify"
            " authenticity of the data sent by UE."
        ),
    )

    # Webhook URLs
    webhook_url = models.URLField(blank=True, default="")
    payment_process_redirect_url = models.URLField(blank=True, default="")

    objects = SafeDeleteManager()
    all_objects = models.Manager()

    def __str__(self):
        """Return string representation of the system"""
        return f"{self.name} ({self.id})"

    def save(self, *args, **kwargs):
        """Save the product. Create a slug if it doesn't already exist."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


@reversion.register(exclude=("created_on", "updated_on"))
class Product(SafeDeleteModel, SoftDeleteActiveModel, TimestampedModel):
    """
    Represents a purchasable product in the system. These include a blob of JSON
    containing system-specific information for the product.
    """

    sku = models.CharField(max_length=255, help_text="SKU of the product.")
    name = models.CharField(
        max_length=255, help_text="Short name of the product, displayed in carts/etc."
    )
    price = models.DecimalField(
        max_digits=7, decimal_places=2, help_text="Price (decimal to two places)"
    )
    description = models.TextField(help_text="Long description of the product.")
    system = models.ForeignKey(
        IntegratedSystem,
        on_delete=models.DO_NOTHING,
        related_name="products",
        help_text="Owner system of the product.",
    )
    system_data = models.JSONField(
        blank=True,
        null=True,
        help_text="System-specific data for the product (in JSON).",
    )
    image_metadata = models.JSONField(
        blank=True,
        null=True,
        help_text="Image metadata including URL, alt text, and description (in JSON).",
    )

    objects = SafeDeleteManager()
    all_objects = models.Manager()

    def save(self, *args, **kwargs):
        # Retrieve image data from the API
        try:
            response = requests.get(
                f"{settings.MITOL_LEARN_API_URL}learning_resources/",
                params={"platform": self.system.slug, "readable_id": self.sku},
                timeout=10,
            )
            response.raise_for_status()
            results_data = response.json()
            course_data = results_data.get("results")[0]
            image_data = course_data.get("image")
            self.image_metadata = {
                "imageURL": image_data.get("url"),
                "alt_text": image_data.get("alt"),
                "description": image_data.get("description"),
            }
        except requests.RequestException:
            log.exception("Error retrieving image data for product %s", self.sku)

        super().save(*args, **kwargs)

    class Meta:
        """Meta class for Product"""

        constraints = [
            models.UniqueConstraint(
                fields=["sku", "system"],
                name="unique_purchasable_sku_per_system",
            )
        ]

    def __str__(self):
        """Return string representation of the product"""

        return f"{self.sku} - {self.system.name} - {self.name} ${self.price}"

    @staticmethod
    def resolve_product_version(product, product_version=None):
        """
        Resolve the specified version of the product. Specify None to indicate the
        current version.

        Returns: Product; either the product you passed in or the version of the product
        you requested.
        """
        if product_version is None:
            return product

        versions = reversion.models.Version.objects.get_for_object(product)

        if versions.count() == 0:
            return product

        for test_version in versions.all():
            if test_version == product_version:
                return Product(
                    id=test_version.field_dict["id"],
                    sku=test_version.field_dict["sku"],
                    name=test_version.field_dict["name"],
                    price=test_version.field_dict["price"],
                    description=test_version.field_dict["description"],
                    system=IntegratedSystem.objects.get(
                        pk=test_version.field_dict["system_id"]
                    ),
                    system_data=test_version.field_dict["system_data"],
                    deleted_on=test_version.field_dict["deleted_on"],
                    deleted_by_cascade=test_version.field_dict["deleted_by_cascade"],
                )

        exception_message = "Invalid product version specified"
        raise TypeError(exception_message)

    @cached_property
    def price_money(self):
        """Return the item price as a quantized decimal."""

        return quantize_decimal(self.price)


class IntegratedSystemAPIKey(AbstractAPIKey):
    """API key for an integrated system"""

    name = models.CharField(max_length=100, unique=True)
    integrated_system = models.ForeignKey(
        "IntegratedSystem", on_delete=models.CASCADE, related_name="api_keys"
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = "Integrated System API Key"
        verbose_name_plural = "Integrated System API Keys"
