# Generated by Django 4.2.16 on 2024-10-16 18:16

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0003_alter_order_state"),
    ]

    def _delete_existing_baskets(apps, scheme_editor):  # noqa: ARG002, N805
        model = apps.get_model("payments", "basket")
        model.objects.all().delete()

    operations = [
        migrations.RunPython(_delete_existing_baskets),
    ]
