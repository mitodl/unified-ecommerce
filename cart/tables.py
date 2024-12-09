import django_tables2 as tables
from payments.models import Order

class OrderTable(tables.Table):
    """Table for displaying a list of orders."""

    number_of_items = tables.Column(accessor="lines.count",
                                    verbose_name="Number of Lines")
    system = tables.Column(accessor="lines.first.product.system.name",
                           verbose_name="System")

    class Meta:
        model = Order
        template_name = "django_tables2/bootstrap.html"
        fields = ("reference_number", "state", "created_on", "system",
                  "total_price_paid", "number_of_items")
        sequence = ("reference_number", "state", "number_of_items", "created_on",
                    "system", "total_price_paid")