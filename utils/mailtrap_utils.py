import mailtrap as mt


def send_message(
    message_content: str,
    to_address: str,
    api_key: str,
    subject: str = "Daily arxiv Digest (DaD)",
):
    # create mail object
    mail = mt.Mail(
        sender=mt.Address(email="mailtrap@stanley-wu.com", name="Cheng Xin's Babel"),
        to=[mt.Address(email=to_address)],
        subject=subject,
        html=message_content,
    )

    # create client and send
    client = mt.MailtrapClient(token=api_key)
    client.send(mail)
