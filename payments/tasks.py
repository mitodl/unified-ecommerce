from main.celery import app

@app.task
def notify_order_payment_successful_email(
    order_id, email_subject, email_body
):
    