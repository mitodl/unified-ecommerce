# Generated by Django 4.2.16 on 2024-10-28 12:59

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0008_alter_discount_integrated_system"),
    ]

    operations = [
        migrations.AddField(
            model_name="basket",
            name="discounts",
            field=models.ManyToManyField(related_name="basket", to="payments.discount"),
        ),
    ]
