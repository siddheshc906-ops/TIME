# backend/core/dependencies.py

import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import certifi

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logger = logging.getLogger(__name__)

SECRET_KEY = os.environ.get("JWT_SECRET", "")
ALGORITHM  = "HS256"

security = HTTPBearer()

# ── Lazy DB reference (set by main.py after connection) ──────────────────────
_db = None

def set_db(database):
    """Called from main.py after MongoDB connects."""
    global _db
    _db = database

def get_db():
    if _db is None:
        raise RuntimeError("Database not initialised — call set_db() first")
    return _db


# ── Token decoder ─────────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT. Returns the payload dict.
    Raises HTTPException 401 on any failure.
    """
    if not SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: JWT_SECRET not set",
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"JWT decode failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── Main dependency ───────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Resolves the current user from the JWT Bearer token.

    Supports ALL three token formats that Timevora issues:
      1. Email/password login  → {"sub": email, "user_id": "<mongo_id>", "email": email}
      2. Google OAuth          → {"sub": email, "user_id": "<mongo_id>", "email": email}
      3. Phone OTP             → {"sub": phone_email, "user_id": "<mongo_id>", "email": phone_email}
      4. Legacy email tokens   → {"user_id": "<mongo_id>", "email": email}   (no sub — old tokens)
      5. Legacy google/phone   → {"sub": email}                               (no user_id — old tokens)

    Lookup strategy (in order):
      a) Use user_id (MongoDB _id) if present — fastest and most precise.
      b) Fall back to sub / email field — for old tokens issued before the fix.
    """
    token   = credentials.credentials
    payload = decode_token(token)

    db    = get_db()
    users = db.users

    # ── Strategy A: look up by MongoDB _id (new tokens) ──────────────────────
    user_id = payload.get("user_id")
    if user_id:
        try:
            user = await users.find_one({"_id": ObjectId(user_id)})
            if user:
                return user
        except Exception:
            pass  # invalid ObjectId — fall through to email lookup

    # ── Strategy B: look up by email / sub (old tokens or fallback) ──────────
    email = payload.get("sub") or payload.get("email")
    if email:
        user = await users.find_one({"email": email})
        if user:
            return user

    # ── Nothing found ─────────────────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="User not found — please log in again",
        headers={"WWW-Authenticate": "Bearer"},
    )