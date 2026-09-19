import hashlib
import hmac
import os
import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import Session, User, now

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError("SECRET_KEY must be set (>=32 chars) in backend/.env — see .env.example")
TOKEN_HOURS = 12
ITERATIONS = 600_000


def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f"pbkdf2${ITERATIONS}${salt}${h}"


def verify_password(pw: str, stored: str) -> bool:
    _, it, salt, h = stored.split("$")
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), int(it)).hex(), h)


def make_token(user: User) -> str:
    return jwt.encode({"sub": str(user.id), "role": user.role, "exp": now() + timedelta(hours=TOKEN_HOURS)}, SECRET_KEY, "HS256")


bearer = HTTPBearer(auto_error=False)


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if not cred:
        raise HTTPException(401, "Not authenticated")
    try:
        uid = int(jwt.decode(cred.credentials, SECRET_KEY, ["HS256"])["sub"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    with Session() as db:
        user = db.get(User, uid)
    if not user:
        raise HTTPException(401, "User no longer exists")
    return user


def officer(user: User = Depends(current_user)) -> User:
    if user.role != "officer":
        raise HTTPException(403, "Officer role required")
    return user
