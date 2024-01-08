"""System metadata models - integrated systems and the data surrounding them"""

import logging

import reversion
from django.contrib.auth import get_user_model
from django.db import models
from mitol.common.models import TimestampedModel

User = get_user_model()
log = logging.getLogger(__name__)


class SoftDeleteTimestampedModel(TimestampedModel):
    """Model that blocks delete and instead marks the items is_active flag as false"""

    is_active = models.BooleanField(default=True)

    def delete(self):
        """Mark items inactive instead of deleting them"""
        self.is_active = False
        self.save(update_fields=["is_active"])

    class Meta:
        """Meta options for SoftDeleteTimestampModel"""

        abstract = True


class ActiveUndeleteManager(models.Manager):
    """Query manager for products"""

    def get_queryset(self):
        """Get the active queryset for manager"""
        return models.QuerySet(self.model, using=self._db).filter(is_active=True)


class IntegratedSystem(SoftDeleteTimestampedModel):
    """Represents an integrated system"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    api_key = models.TextField(blank=True)

    all_objects = models.Manager()
    objects = ActiveUndeleteManager()

    def __str__(self):
        """Return string representation of the system"""
        return f"{self.name} ({self.id})"


@reversion.register(exclude=("created_on", "updated_on"))
class Product(SoftDeleteTimestampedModel):
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

    all_objects = models.Manager()
    objects = ActiveUndeleteManager()

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

        return f"{self.sku} - {self.system.name} - {self.name} {self.price}"
