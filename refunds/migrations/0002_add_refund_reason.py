# Generated by Django 4.2.18 on 2025-02-12 16:49

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("refunds", "0001_add_initial_refunds_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="request",
            name="refund_reason",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Reason for refund, supplied by the processing user.",
            ),
        ),
        migrations.AlterField(
            model_name="request",
            name="processed_by",
            field=models.ForeignKey(
                blank=True,
                help_text="The user who processed the request. (Usually blank.)",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="processed_refund_requests",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="request",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "pending"),
                    ("created", "created"),
                    ("denied", "denied"),
                    ("approved", "approved"),
                    ("approved-complete", "approved-complete"),
                    ("failed", "failed"),
                ],
                default="created",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="requestline",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "pending"),
                    ("created", "created"),
                    ("denied", "denied"),
                    ("approved", "approved"),
                    ("approved-complete", "approved-complete"),
                    ("failed", "failed"),
                ],
                default="created",
                help_text="The status of this line item.",
                max_length=20,
            ),
        ),
    ]
