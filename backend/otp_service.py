# backend/otp_service.py
import os
import random
import httpx
from datetime import datetime, timedelta, timezone

MSG91_API_KEY    = os.environ.get("MSG91_API_KEY", "")
MSG91_TEMPLATE_ID = os.environ.get("MSG91_TEMPLATE_ID", "")
OTP_EXPIRY_MINUTES = 10

def generate_otp() -> str:
    """Returns a 6-digit OTP as a string."""
    return str(random.randint(100000, 999999))

async def send_otp_msg91(phone: str, otp: str) -> bool:
    """
    Sends OTP via MSG91.
    phone should be in international format WITHOUT + (e.g. 919876543210)
    Returns True on success, False on failure.
    """
    url = "https://control.msg91.com/api/v5/otp"
    params = {
        "template_id": MSG91_TEMPLATE_ID,
        "mobile":      phone,
        "authkey":     MSG91_API_KEY,
        "otp":         otp,
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, params=params, timeout=10)
    return resp.status_code == 200

def otp_expiry() -> datetime:
    """Returns expiry timestamp OTP_EXPIRY_MINUTES from now (UTC)."""
    return datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)