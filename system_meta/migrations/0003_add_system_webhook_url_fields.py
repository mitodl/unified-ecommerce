# Generated by Django 4.2.10 on 2024-03-11 20:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("system_meta", "0002_add_system_slug"),
    ]

    operations = [
        migrations.AddField(
            model_name="integratedsystem",
            name="sale_refunded_webhook_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="integratedsystem",
            name="sale_succeeded_webhook_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
