"""Generated by Django 4.2.8 on 2023-12-13 21:08"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="IntegratedSystem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("api_key", models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="Product",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("sku", models.CharField(max_length=255)),
                ("price", models.DecimalField(decimal_places=2, max_digits=7)),
                ("description", models.TextField()),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Controls visibility of the product in the app.",
                    ),
                ),
                (
                    "system",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="products",
                        to="system_meta.integratedsystem",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True)),
                fields=("sku", "system"),
                name="unique_purchasable_sku_per_system",
            ),
        ),
    ]