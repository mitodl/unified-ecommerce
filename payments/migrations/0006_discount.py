# Generated by Django 4.2.16 on 2024-10-24 13:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('system_meta', '0005_integratedsystem_payment_process_redirect_url'),
        ('payments', '0005_basket_integrated_system_alter_basket_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='Discount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_on', models.DateTimeField(auto_now_add=True)),
                ('updated_on', models.DateTimeField(auto_now=True)),
                ('amount', models.DecimalField(decimal_places=5, max_digits=20)),
                ('automatic', models.BooleanField(default=False)),
                ('discount_type', models.CharField(choices=[('percent-off', 'percent-off'), ('dollars-off', 'dollars-off'), ('fixed-price', 'fixed-price')], max_length=30)),
                ('redemption_type', models.CharField(choices=[('one-time', 'one-time'), ('one-time-per-user', 'one-time-per-user'), ('unlimited', 'unlimited')], max_length=30)),
                ('payment_type', models.CharField(choices=[('marketing', 'marketing'), ('sales', 'sales'), ('financial-assistance', 'financial-assistance'), ('customer-support', 'customer-support'), ('staff', 'staff'), ('legacy', 'legacy')], max_length=30, null=True)),
                ('max_redemptions', models.PositiveIntegerField(default=0, null=True)),
                ('discount_code', models.CharField(max_length=100)),
                ('activation_date', models.DateTimeField(blank=True, help_text='If set, this discount code will not be redeemable before this date.', null=True)),
                ('expiration_date', models.DateTimeField(blank=True, help_text='If set, this discount code will not be redeemable after this date.', null=True)),
                ('is_bulk', models.BooleanField(default=False)),
                ('integrated_system', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='discounts', to='system_meta.integratedsystem')),
                ('product', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='discounts', to='system_meta.product')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
