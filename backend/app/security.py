"""JWT authentication for the SPRO scaffold.

Roles are a flat placeholder set loosely mirroring the SRS user list
(docs/SRS.md section 2.2). There is no local-open/passwordless mode here
(unlike the Khorasan Petrochemical SEM dashboard on this account) — this is
a plain demo-credential JWT login, matching the convention used by the
other "-60ta" sibling projects. Change ``SECRET_KEY`` and ``DEMO_PASSWORD``
before any real deployment.
"""
from __future__ import annotations

import sqlite3
import time

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from .db import get_conn, one

ROLES = {
    "admin": "مدیر سیستم",
    "process_engineer": "مهندس فرآیند",
    "energy_engineer": "مهندس انرژی و خوراک",
    "quality_engineer": "مهندس کیفیت",
    "operator": "اپراتور",
}
bearer = HTTPBearer(auto_error=False)


def hash_password(pw: str, rounds: int = 12) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds)).decode()


def verify_password(pw: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user: sqlite3.Row) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": user["username"], "role": user["role"], "iat": now, "exp": now + config.TOKEN_TTL_MINUTES * 60},
        config.SECRET_KEY,
        algorithm="HS256",
    )


def current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer),
    conn: sqlite3.Connection = Depends(get_conn),
) -> sqlite3.Row:
    if not cred:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "احراز هویت لازم است")
    try:
        payload = jwt.decode(cred.credentials, config.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "توکن نامعتبر یا منقضی است")
    u = one(conn, "SELECT user_id, username, full_name, role, is_active FROM users WHERE username=?", (payload["sub"],))
    if not u or not u["is_active"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "کاربر غیرفعال است")
    return u


def require(*roles: str):
    """``admin`` is always allowed, regardless of the roles requested."""
    allowed = set(roles) | {"admin"}

    def dep(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
        if user["role"] not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "دسترسی کافی برای این عملیات ندارید")
        return user

    return dep
