import asyncio
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)


def _send_email_sync(recipient: str, otp: str) -> None:
	load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
	host = os.getenv("SMTP_HOST")
	port = int(os.getenv("SMTP_PORT", "587"))
	username = os.getenv("SMTP_USERNAME")
	password = os.getenv("SMTP_PASSWORD")
	sender = os.getenv("SMTP_FROM", username or "")

	if not host or not username or not password or not sender:
		raise RuntimeError(
			"Email is not configured. Set SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM."
		)

	message = EmailMessage()
	message["Subject"] = "Your HemaHub verification code"
	message["From"] = sender
	message["To"] = recipient
	message.set_content(
		f"Your HemaHub verification code is {otp}. It expires in 10 minutes."
	)

	with smtplib.SMTP(host, port, timeout=20) as smtp:
		smtp.starttls()
		smtp.login(username, password)
		smtp.send_message(message)


async def send_otp_email(recipient: str, otp: str) -> None:
	await asyncio.to_thread(_send_email_sync, recipient, otp)
