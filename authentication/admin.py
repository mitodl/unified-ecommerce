"""Django Admin for authentication app"""

from django.contrib import admin

from authentication import models

admin.site.register(models.KeycloakAdminToken)
