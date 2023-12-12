""" System metadata models - integrated systems and the data surrounding them """

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List

import pytz
import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models


User = get_user_model()
log = logging.getLogger(__name__)


class ProductsQuerySet(models.QuerySet):
    """Queryset to block delete and instead mark the items in_active"""

    def delete(self):
        self.update(is_active=False)


class ActiveProducsUndeleteManager(models.Manager):
    """Query manager for products"""

    # This can be used generally, for the models that have `is_active` field
    def get_queryset(self):
        """Getting the active queryset for manager"""
        return ProductsQuerySet(self.model, using=self._db).filter(is_active=True)


class IntegratedSystem(models.Model):
    """Represents an integrated system"""

    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    api_key = models.TextField(blank=True, null=True)

    def __str__(self):
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

    system = models.ForeignKey(IntegratedSystem, on_delete=models.DO_NOTHING, related_name="products")

    objects = ActiveProducsUndeleteManager()
    all_objects = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["object_id", "is_active", "content_type"],
                condition=models.Q(is_active=True),
                name="unique_purchasable_object",
            )
        ]

    def delete(self):
        self.is_active = False
        self.save(update_fields=("is_active",))

    def __str__(self):
        return f"#{self.id} {self.description} {self.price}"
