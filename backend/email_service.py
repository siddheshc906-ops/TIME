import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from pathlib import Path

# Load env
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")


def send_verification_email(to_email, token):
    verify_link = f"http://127.0.0.1:8000/api/verify?token={token}"

    subject = "Timevora — Verify your email"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background:#f9fafb; padding:40px;">
        <div style="max-width:500px;margin:auto;background:white;padding:30px;border-radius:12px;text-align:center;">
          
          <h2 style="color:#4f46e5;">Verify your email</h2>

          <p>Hi 👋</p>

          <p>
            Please verify your email by clicking the button below:
          </p>

          <a href="{verify_link}"
             style="
               display:inline-block;
               margin-top:20px;
               padding:12px 28px;
               background:#4f46e5;
               color:white;
               text-decoration:none;
               border-radius:999px;
               font-weight:bold;
             ">
             Verify Email
          </a>

          
          <p style="margin-top:25px;">
            Thanks!  
            <br/>— Team Timevora
          </p>

          <p style="margin-top:30px;font-size:12px;color:#888;">
            If you didn’t create this account, you can ignore this email.
          </p>

        </div>
      </body>
    </html>
    """

    msg = MIMEMultipart()
    msg["From"] = f"Timevora <{EMAIL_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
