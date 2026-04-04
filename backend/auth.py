from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import os

pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto"
)

def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

def verify_google_token(token: str) -> dict:
    """
    Verifies a Google ID token and returns the decoded payload.
    Returns dict with keys: sub, email, name, picture
    Raises ValueError if token is invalid.
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        client_id
    )
    return {
        "sub": idinfo["sub"],           # unique Google user ID
        "email": idinfo["email"],
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", "")
    }