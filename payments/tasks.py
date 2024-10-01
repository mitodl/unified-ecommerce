from unified_ecommerce.celery import app
from payments.mail_api import send_successful_order_payment_email

@app.task
def successful_order_payment_email_task(
    order_id, email_subject, email_body
):
    from payments.models import Order
    order = Order.objects.get(id=order_id)
    send_successful_order_payment_email(order, email_subject, email_body)
