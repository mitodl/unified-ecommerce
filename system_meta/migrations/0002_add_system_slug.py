# Generated by Django 4.2.8 on 2024-01-11 16:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("system_meta", "0001_add_integrated_system_and_product_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="integratedsystem",
            name="slug",
            field=models.CharField(blank=True, max_length=80, null=True, unique=True),
        ),
    ]
