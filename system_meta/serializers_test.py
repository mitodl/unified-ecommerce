"""Serializers tests for system metadata."""

import pytest

from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.models import IntegratedSystem, Product
from system_meta.serializers import (
    AdminIntegratedSystemSerializer,
    IntegratedSystemSerializer,
    ProductSerializer,
)
from unified_ecommerce.test_utils import BaseSerializerTest

pytestmark = pytest.mark.django_db


class TestAdminIntegratedSystemSerializer(BaseSerializerTest):
    """Tests for the IntegratedSystemSerializer."""

    serializer_class = AdminIntegratedSystemSerializer
    factory_class = IntegratedSystemFactory
    model_class = IntegratedSystem
    queryset = IntegratedSystem.all_objects


class TestIntegratedSystemSerializer(BaseSerializerTest):
    """Tests for the IntegratedSystemSerializer."""

    serializer_class = IntegratedSystemSerializer
    factory_class = IntegratedSystemFactory
    model_class = IntegratedSystem
    queryset = IntegratedSystem.all_objects
    only_fields = ["id", "name", "slug", "description"]


class TestProductSerializer(BaseSerializerTest):
    """Tests for the ProductSerializer."""

    serializer_class = ProductSerializer
    factory_class = ProductFactory
    model_class = Product
    queryset = Product.all_objects
