from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0006_discount_line_discounted_price_redeemeddiscount_and_more"),
    ]

    def _populate_existing_line_discount_price(apps, scheme_editor):  # noqa: ARG002, N805
        model = apps.get_model("payments", "line")
        for line in model.objects.all():
            line.discounted_price = line.total_price
            line.save()

    operations = [
        migrations.RunPython(_populate_existing_line_discount_price),
    ]
