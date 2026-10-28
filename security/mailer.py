"""
One-time password (OTP) generation and delivery for the forgot-password
flow. Sending goes through Gmail's SMTP relay using an account you control
— see the README for how to set GMAIL_ADDRESS and GMAIL_APP_PASSWORD.

Two failure modes are handled differently on purpose:

  - Missing/wrong GMAIL_* configuration is a setup problem, true for every
    request regardless of who's asking, so EmailNotConfiguredError is
    allowed to surface as a clear, specific message.
  - A send that fails for some other reason (Gmail hiccup, bad recipient
    address) is caught, logged server-side, and swallowed by the caller —
    see blueprints/auth.py's forgot_password route. Revealing that a send
    specifically failed would tell an attacker the email address exists,
    which is exactly what the generic "if that email is on file..."
    response is designed to avoid.
"""
import os
import secrets
import smtplib
from email.mime.text import MIMEText


class EmailNotConfiguredError(Exception):
    """Raised when GMAIL_ADDRESS / GMAIL_APP_PASSWORD aren't set."""


def is_email_configured():
    return bool(os.environ.get("GMAIL_ADDRESS")) and bool(os.environ.get("GMAIL_APP_PASSWORD"))


def generate_otp():
    """A 6-digit numeric code from the 'secrets' module, not 'random' —
    'random' is a predictable PRNG and must never be used for anything
    security-sensitive, even something as short-lived as this."""
    return "".join(secrets.choice("0123456789") for _ in range(6))


def send_otp_email(to_email, otp_code, full_name):
    if not is_email_configured():
        raise EmailNotConfiguredError(
            "GMAIL_ADDRESS and GMAIL_APP_PASSWORD are not set. "
            "See the README for how to create a Gmail App Password."
        )

    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    body = (
        f"Hi {full_name},\n\n"
        f"Your Secure Cafe POS password reset code is: {otp_code}\n\n"
        f"This code expires in 10 minutes and can only be used once. "
        f"If you didn't request this, you can ignore this email — your "
        f"password will not be changed.\n"
    )
    msg = MIMEText(body)
    msg["Subject"] = "Secure Cafe POS — Your password reset code"
    msg["From"] = gmail_address
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
        server.starttls()
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, [to_email], msg.as_string())
