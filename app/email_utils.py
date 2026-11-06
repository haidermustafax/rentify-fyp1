import os
import secrets
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")

def generate_otp() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def send_otp_email(to_email: str, otp_code: str, purpose: str = "Sign-Up Verification"):
    subject = f"Rentify - Your {purpose} Code"
    body = f"""Hello,

Your Rentify verification code ({purpose}) is:

===========================
         {otp_code}
===========================

This code is valid for 10 minutes.

Best regards,
The Rentify Team
"""

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError("SMTP is not configured. Set SENDER_EMAIL and SENDER_PASSWORD in .env.")

    msg = MIMEMultipart()
    msg["From"] = f"Rentify Platform <{SENDER_EMAIL}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
        server.starttls(context=context)
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
