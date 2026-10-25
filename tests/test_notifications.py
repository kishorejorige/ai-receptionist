from unittest.mock import Mock

from app import notifications


def test_send_owner_booking_alert_uses_smtp(monkeypatch):
    for key, value in {
        "OWNER_EMAIL": "owner@example.com",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_PORT": "587",
        "SMTP_SECURITY": "starttls",
        "SMTP_FROM": "receptionist@example.com",
        "SMTP_USERNAME": "mailer",
        "SMTP_PASSWORD": "not-a-real-password",
    }.items():
        monkeypatch.setenv(key, value)

    server = Mock()
    smtp_context = Mock()
    smtp_context.__enter__ = Mock(return_value=server)
    smtp_context.__exit__ = Mock(return_value=None)
    smtp = Mock(return_value=smtp_context)
    monkeypatch.setattr(notifications.smtplib, "SMTP", smtp)
    create_context = Mock()
    monkeypatch.setattr(notifications.ssl, "create_default_context", create_context)

    notifications.send_owner_booking_alert(
        "Smile Dental Clinic",
        "Alex Patient",
        "1234567890",
        "Consultation",
        "2026-10-26",
        "10:00",
    )

    smtp.assert_called_once_with("smtp.example.com", 587, timeout=10)
    server.starttls.assert_called_once_with(context=create_context.return_value)
    server.login.assert_called_once_with("mailer", "not-a-real-password")
    message = server.send_message.call_args.args[0]
    assert message["To"] == "owner@example.com"
    assert "Alex Patient" in message.get_content()
    assert "1234567890" in message.get_content()
    assert "10:00" in message.get_content()
