"""System metadata models - integrated systems and the data surrounding them"""

import logging

import reversion
from django.contrib.auth import get_user_model
from django.db import models
from mitol.common.models import TimestampedModel
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
    api_key = models.TextField(blank=True)

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

    objects = SafeDeleteManager()
    all_objects = models.Manager()

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

    def delete(self):
        """Mark the product inactive instead of deleting it"""

        self.is_active = False
        self.save(update_fields=("is_active",))

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

        versions = reversion.Version.objects.get_for_object(product)

        if versions.count() == 0:
            return product

        for test_version in versions.all():
            if test_version == product_version:
                return Product(
                    id=test_version.field_dict["id"],
                    price=test_version.field_dict["price"],
                    description=test_version.field_dict["description"],
                    is_active=test_version.field_dict["is_active"],
                )

        exception_message = "Invalid product version specified"
        raise TypeError(exception_message)
