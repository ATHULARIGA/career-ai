import smtplib
import os
from email.mime.text import MIMEText

def send_mail(to, link=None, subject=None, body=None):
    default_subject = "Mock Interview Booking"
    default_body = f"""
Your Mock Interview is Scheduled!

Join Here:
{link or "Link unavailable"}
"""

    msg = MIMEText(body or default_body)
    msg['Subject'] = subject or default_subject
    msg['From'] = os.getenv("SMTP_USER")
    msg['To'] = to

    try:
        server = smtplib.SMTP("smtp-relay.brevo.com", 587)
        server.starttls()
        server.login(
            os.getenv("SMTP_USER"),
            os.getenv("SMTP_PASS")
        )
        server.send_message(msg)
        server.quit()
        print("MAIL SENT")
        return True
    except Exception as e:
        print("MAIL ERROR:", e)
        return False
