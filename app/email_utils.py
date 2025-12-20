import os
import requests

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL")
CEO_EMAIL = os.getenv("CEO_EMAIL")


def send_email(to_email: str, subject: str, html_body: str):
    if not BREVO_API_KEY:
        return

    sender_email = FROM_EMAIL.split("<")[-1].replace(">", "").strip()

    url = "https://api.brevo.com/v3/smtp/email"

    payload = {
        "sender": {
            "email": sender_email,
            "name": "CEO Task System"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body
    }

    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()