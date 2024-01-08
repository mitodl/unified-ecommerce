"""Django Admin for system_meta app"""

from django.contrib import admin

from system_meta.models import IntegratedSystem, Product

admin.site.register(IntegratedSystem)
admin.site.register(Product)
