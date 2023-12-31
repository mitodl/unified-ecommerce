# Generated by Django 2.2.13 on 2020-07-27 20:43

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("authentication", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="BlockedIPRange",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_on", models.DateTimeField(auto_now_add=True)),
                ("updated_on", models.DateTimeField(auto_now=True)),
                ("ip_start", models.GenericIPAddressField()),
                ("ip_end", models.GenericIPAddressField()),
            ],
            options={"abstract": False},
        )
    ]
