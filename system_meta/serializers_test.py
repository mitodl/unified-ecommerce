"""Serializers tests for system metadata."""

import pytest

from system_meta.factories import IntegratedSystemFactory, ProductFactory
from system_meta.serializers import IntegratedSystemSerializer, ProductSerializer
from unified_ecommerce.test_utils import BaseSerializerTest

pytestmark = pytest.mark.django_db


class TestIntegratedSystemSerializer(BaseSerializerTest):
    """Tests for the IntegratedSystemSerializer."""

    serializer_class = IntegratedSystemSerializer
    factory_class = IntegratedSystemFactory


class TestProductSerializer(BaseSerializerTest):
    """Tests for the ProductSerializer."""

    serializer_class = ProductSerializer
    factory_class = ProductFactory
