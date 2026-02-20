import smtplib
import os
from email.mime.text import MIMEText

def send_mail(to, link):

    msg = MIMEText(f"""
Your Mock Interview is Scheduled!

Join Here:
{link}
""")

    msg['Subject'] = "Mock Interview Booking"
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

        return True

    except Exception as e:
        print("MAIL ERROR:", e)
        return False
