"""System metadata models - integrated systems and the data surrounding them"""

import logging

import reversion
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()
log = logging.getLogger(__name__)


class ProductsQuerySet(models.QuerySet):
    """Queryset to block delete and instead mark the items in_active"""

    def delete(self):
        """Mark items inactive instead of deleting them"""
        self.update(is_active=False)


class ActiveProducsUndeleteManager(models.Manager):
    """Query manager for products"""

    def get_queryset(self):
        """Get the active queryset for manager"""
        return ProductsQuerySet(self.model, using=self._db).filter(is_active=True)


class IntegratedSystem(models.Model):
    """Represents an integrated system"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    api_key = models.TextField(blank=True)

    def __str__(self):
        """Return string representation of the system"""
        return f"{self.name} ({self.id})"


@reversion.register(exclude=("created_on", "updated_on"))
class Product(models.Model):
    """
    Represents a purchasable product in the system. These include a blob of JSON
    containing system-specific information for the product.

    TODO: this should be a TimestampedModel when ol-django is ready for Django 4
    """

    sku = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=7, decimal_places=2, help_text="")
    description = models.TextField()
    is_active = models.BooleanField(
        default=True,
        null=False,
        help_text="Controls visibility of the product in the app.",
    )
    system = models.ForeignKey(
        IntegratedSystem, on_delete=models.DO_NOTHING, related_name="products"
    )

    all_objects = models.Manager()
    objects = ActiveProducsUndeleteManager()

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

        return f"#{self.id} {self.description} {self.price}"

    def delete(self):
        """Mark the product inactive instead of deleting it"""

        self.is_active = False
        self.save(update_fields=("is_active",))
