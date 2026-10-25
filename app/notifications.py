import os
import smtplib
import ssl
from email.message import EmailMessage


def send_owner_booking_alert(
    clinic_name: str,
    patient_name: str,
    phone: str,
    treatment: str,
    day: str,
    slot: str,
) -> None:
    owner_email = os.getenv("OWNER_EMAIL")
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM")
    if not owner_email or not host or not sender:
        raise RuntimeError("OWNER_EMAIL, SMTP_HOST, and SMTP_FROM must be configured")

    username = os.getenv("SMTP_USERNAME")
    password = os.getenv("SMTP_PASSWORD")
    if bool(username) != bool(password):
        raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")

    security = os.getenv("SMTP_SECURITY", "starttls").lower()
    if security not in {"starttls", "ssl", "none"}:
        raise ValueError("SMTP_SECURITY must be starttls, ssl, or none")
    port = int(os.getenv("SMTP_PORT", "587"))
    message = EmailMessage()
    message["Subject"] = f"New appointment booking - {clinic_name}"
    message["From"] = sender
    message["To"] = owner_email
    message.set_content(
        f"New appointment booking for {clinic_name}:\n"
        f"Patient: {patient_name}\n"
        f"Phone: {phone}\n"
        f"Treatment: {treatment}\n"
        f"Date: {day}\n"
        f"Time: {slot}\n"
    )

    if security == "ssl":
        with smtplib.SMTP_SSL(
            host, port, timeout=10, context=ssl.create_default_context()
        ) as server:
            if username:
                server.login(username, password)
            server.send_message(message)
        return

    with smtplib.SMTP(host, port, timeout=10) as server:
        if security == "starttls":
            server.starttls(context=ssl.create_default_context())
        if username:
            server.login(username, password)
        server.send_message(message)
