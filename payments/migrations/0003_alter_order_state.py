# Generated by Django 4.2.15 on 2024-09-23 15:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0002_remove_system_slug_from_basket'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='state',
            field=models.CharField(choices=[('pending', 'Pending'), ('fulfilled', 'Fulfilled'), ('canceled', 'Canceled'), ('refunded', 'Refunded'), ('declined', 'Declined'), ('errored', 'Errored'), ('review', 'Review')], default='pending'),
        ),
    ]
