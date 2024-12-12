from celery import shared_task
from .models import Product

@shared_task
def update_products():
    """Update all product's image metadata"""
    products = Product.objects.all()
    for product in products:
        product.save()