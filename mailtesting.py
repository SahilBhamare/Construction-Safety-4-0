import os
import smtplib
from dotenv import load_dotenv
from email.mime.text import MIMEText

load_dotenv(override=True)
def test_email():
    msg = MIMEText("This is a test email from your PPE detection system")
    msg["Subject"] = "Test Email"
    msg["From"] = os.getenv("SENDER_EMAIL")
    msg["To"] = os.getenv("RECEIVER_EMAIL")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(os.getenv("SENDER_EMAIL"), os.getenv("EMAIL_PASSWORD"))
            server.sendmail(os.getenv("SENDER_EMAIL"), [os.getenv("RECEIVER_EMAIL")], msg.as_string())
        print("Test email sent successfully!")
    except Exception as e:
        print(f"{ msg["From"]}-->{msg["To"]}-->{ msg["Subject"]}Failed to send test email: {e}")

test_email()