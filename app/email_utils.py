import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")
CEO_EMAIL = os.getenv("CEO_EMAIL")


def send_email(to_email: str, subject: str, html_body: str, cc: str | None = None):
    if not all([SMTP_HOST, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL]):
        # Fail silently to avoid breaking app
        return

    msg = MIMEMultipart()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    if cc:
        msg["Cc"] = cc

    msg.attach(MIMEText(html_body, "html"))

    recipients = [to_email]
    if cc:
        recipients.append(cc)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, recipients, msg.as_string())