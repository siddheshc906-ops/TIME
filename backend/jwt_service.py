# backend/jwt_service.py
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from jose import jwt

# ── Load .env BEFORE reading any variables ────────────────────────────────────
# jwt_service.py is imported at module level before main.py runs load_dotenv(),
# so we load the .env file here directly.
load_dotenv(Path(__file__).resolve().parent / ".env")

# -------------------- CONFIG --------------------

SECRET_KEY = os.environ.get("JWT_SECRET", "")
ALGORITHM  = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7   # 7 days

if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET not set — check your .env file")

# -------------------- TOKEN CREATION --------------------

def create_access_token(data: dict) -> str:
    """
    Create a signed JWT containing `data`.
    Adds an `exp` claim automatically (7 days from now).
    """
    to_encode = data.copy()
    expire    = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)