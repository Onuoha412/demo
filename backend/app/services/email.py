import smtplib
import ssl
from email.message import EmailMessage

from ..config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when a configured password reset email cannot be delivered."""


def send_password_reset(email: str, reset_url: str) -> None:
    subject = "Reset your QueueLess password"
    body = (
        "QueueLess\n\n"
        "Password Reset\n\n"
        "Someone requested a password reset for your QueueLess account.\n\n"
        f"Reset Password: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    if settings.email_mode == "console":
        if settings.environment == "production":
            raise EmailDeliveryError("Console email delivery is disabled in production")
        print(f"QueueLess password reset for {email}: {reset_url}")
        return
    if not settings.smtp_host or not settings.smtp_from:
        raise EmailDeliveryError("SMTP email delivery is not configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
            client.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password or "")
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise EmailDeliveryError("Password reset email could not be delivered") from error
