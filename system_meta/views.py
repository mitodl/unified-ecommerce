"""Views for the REST API for system metadata."""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from system_meta.models import IntegratedSystem, Product
from system_meta.serializers import IntegratedSystemSerializer, ProductSerializer


class IntegratedSystemViewSet(viewsets.ModelViewSet):
    """Viewset for IntegratedSystem model."""

    queryset = IntegratedSystem.objects.all()
    serializer_class = IntegratedSystemSerializer
    permission_classes = (IsAuthenticated,)


class ProductViewSet(viewsets.ModelViewSet):
    """Viewset for Product model."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = (IsAuthenticated,)
