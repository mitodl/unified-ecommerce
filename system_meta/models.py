"""System metadata models - integrated systems and the data surrounding them"""

import logging

import reversion
from django.contrib.auth import get_user_model
from django.db import models
from mitol.common.models import TimestampedModel

User = get_user_model()
log = logging.getLogger(__name__)


class SoftDeleteQuerySet(models.QuerySet):
    """Queryset to block delete and instead mark the items in_active"""

    def delete(self):
        """Mark items inactive instead of deleting them"""
        self.update(is_active=False)


class ActiveUndeleteManager(models.Manager):
    """Query manager for products"""

    def get_queryset(self):
        """Get the active queryset for manager"""
        return SoftDeleteQuerySet(self.model, using=self._db).filter(is_active=True)


class IntegratedSystem(TimestampedModel):
    """Represents an integrated system"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    api_key = models.TextField(blank=True)

    all_objects = models.Manager()
    objects = ActiveUndeleteManager()

    def __str__(self):
        """Return string representation of the system"""
        return f"{self.name} ({self.id})"

    def delete(self):
        """Mark the product inactive instead of deleting it"""

        self.is_active = False
        self.save(update_fields=("is_active",))


@reversion.register(exclude=("created_on", "updated_on"))
class Product(TimestampedModel):
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
    is_active = models.BooleanField(
        default=True,
        null=False,
        help_text="Controls visibility of the product in the app.",
    )
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
                condition=models.Q(is_active=True),
                name="unique_purchasable_sku_per_system",
            )
        ]

    def __str__(self):
        """Return string representation of the product"""

        return f"{self.sku} - {self.system.name} - {self.name} {self.price}"

    def delete(self):
        """Mark the product inactive instead of deleting it"""

        self.is_active = False
        self.save(update_fields=("is_active",))