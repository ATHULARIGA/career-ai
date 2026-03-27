import smtplib
import os
import json
import urllib.request
import urllib.error
from email.mime.text import MIMEText
from dotenv import load_dotenv

def send_mail(to, link=None, subject=None, body=None):
    load_dotenv(override=True)
    default_subject = "Mock Interview Booking"
    default_body = f"""
Your Mock Interview is Scheduled!

Join Here:
{link or "Link unavailable"}
"""

    msg = MIMEText(body or default_body)
    msg['Subject'] = subject or default_subject
    smtp_user = (os.getenv("SMTP_USER") or "").strip()
    smtp_pass = os.getenv("SMTP_PASS") or ""
    smtp_host = (os.getenv("SMTP_HOST") or "smtp-relay.brevo.com").strip()
    smtp_port = int(os.getenv("SMTP_PORT") or 587)
    brevo_api_key = (os.getenv("BREVO_API_KEY") or "").strip()
    sender_email = (os.getenv("SENDER_EMAIL") or smtp_user).strip()
    sender_name = (os.getenv("SENDER_NAME") or "ResuMate").strip()

    if brevo_api_key and sender_email:
        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": to}],
            "subject": subject or default_subject,
            "textContent": body or default_body,
        }
        req = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "accept": "application/json",
                "api-key": brevo_api_key,
                "content-type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                if 200 <= resp.status < 300:
                    print("MAIL SENT (BREVO API)")
                    return True
                print("MAIL ERROR (BREVO API):", resp.status)
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            print("MAIL ERROR (BREVO API):", e.code, error_body)
        except Exception as e:
            print("MAIL ERROR (BREVO API):", e)

    if not smtp_user or not smtp_pass:
        print("MAIL ERROR: Missing SMTP credentials and Brevo API send failed/unavailable.")
        return False

    msg['From'] = smtp_user
    msg['To'] = to

    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=20)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        print("MAIL SENT")
        return True
    except Exception as e:
        print("MAIL ERROR:", e)
        return False
