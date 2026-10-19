"""Authentication: password hashing, JWT tokens and FastAPI dependencies.

Multi-tenant scheme: every professor owns their subjects and chat sessions.
Tokens are signed with HS256 (secret from AUTH_SECRET env, required in
production). Passwords use PBKDF2-HMAC-SHA256 (hashlib, no extra deps).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session as OrmSession

from core.domain.models import User

ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 12 * 60  # 12h session
_PBKDF2_ITERATIONS = 240_000

_bearer = HTTPBearer(auto_error=False)


class AuthError(Exception):
    """Raised by the service layer; routers map it to HTTP errors."""


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256, format: pbkdf2$iterations$salt$hash)
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------
def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid token") from e


def _secret() -> str:
    secret = os.environ.get("AUTH_SECRET", "")
    if not secret:
        # Dev fallback so local runs don't crash; production must set AUTH_SECRET.
        secret = "dev-insecure-secret-change-me-in-production-0123456789"
    return secret


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
def get_db() -> OrmSession:
    from core.infrastructure.db.connection import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: OrmSession = Depends(get_db),
) -> User:
    """Resolves the authenticated user from the Bearer token."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.get(User, uuid.UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user
