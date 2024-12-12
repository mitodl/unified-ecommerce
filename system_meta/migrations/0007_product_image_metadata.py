# Generated by Django 4.2.17 on 2024-12-10 16:10

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("system_meta", "0006_integratedsystemapikey"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="image_metadata",
            field=models.JSONField(
                blank=True,
                help_text="Image metadata including URL, alt text, and description (in JSON).",
                null=True,
            ),
        ),
    ]