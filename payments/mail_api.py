

def send_order_payment_successful_email(
    financial_assistance_request, email_subject, email_body
):
    try:
        with get_message_sender(FlexiblePriceStatusChangeMessage) as sender:
            sender.build_and_send_message(
                financial_assistance_request.user.email,
                {
                    "subject": email_subject,
                    "first_name": financial_assistance_request.user.legal_address.first_name,
                    "message": email_body,
                    "program_name": financial_assistance_request.courseware_object.title,
                },
            )
    except:  # noqa: E722
        log.exception("Error sending flexible price request status change email")